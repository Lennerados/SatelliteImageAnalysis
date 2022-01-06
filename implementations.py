from interfaces import *
from xml.etree import ElementTree as ET
from rasterio.io import MemoryFile
from pathlib import Path

import requests
import configparser
import json
import numpy as np

c = configparser.ConfigParser()
c.read("config.ini")
user = c["DEFAULT"]["username"]
pw = c["DEFAULT"]["password"]
savefilename = c["DEFAULT"]["savefilename"]
querySize = int(c["DEFAULT"]["querysize"])
maxcloudcoverage = float(c["DEFAULT"]["maxcloudcoverage"])

savefilelock = Lock()


class CountDispatcher(Dispatcher):
    # TODO: Put the default update method already in the interface and just override the getWorkerThread() method instead
    def getWorkerThread(self, data):
        return CountWorkerThread(self, data)


class CountWorkerThread(WorkerThread):
    def run(self):
        d = self.data
        # Only takes Sentinel-2-Data in the advances process Level L2A
        query = (
            "https://scihub.copernicus.eu/dhus/search?q=filename:S2?_* AND beginposition:["
            + str(d[1].year)
            + "-"
            + str(d[1].month)
            + "-"
            + str(d[1].day)
            + "T00:00:00.000Z TO "
            + str(d[2].year)
            + "-"
            + str(d[2].month)
            + "-"
            + str(d[2].day)
            + "T00:00:00.000Z] AND "
            + "cloudcoverpercentage:[0 TO "
            + str(d[3])
            + '] AND footprint:"Intersects(POLYGON(('
        )
        for i in range(len(d[0])):
            query = query + str(d[0][i][0]) + " " + str(d[0][i][1]) + ", "
        # Adds the same coordinate again in order to create a loop (needed for the query)
        query = query + str(d[0][0][0]) + " " + str(d[0][0][1]) + ')))"&format=json'
        print(query)
        # Asks once for the query to check how many results there are, splits the query in pices and puts
        # them into the next pipeline
        r = requests.get(query, auth=(user, pw))
        r.raise_for_status()
        j = r.json()
        count = int(j["feed"]["opensearch:totalResults"])
        print("First Query: " + j["feed"]["subtitle"])
        for i in range(((count - 1) // querySize) + 1):
            # attach and put to the queue
            self.dispatcher.addData(
                query + "&start=" + str(i * querySize) + "&rows=" + str(querySize)
            )


class QueryDispatcher(Dispatcher):
    def getWorkerThread(self, data):
        return QueryWorkerThread(self, data)


class QueryWorkerThread(WorkerThread):
    def run(self):
        query = self.data
        r = requests.get(query, auth=(user, pw))
        r.raise_for_status()
        j = r.json()
        productList = []
        # Adds all needed information about the products so they can be downloaded by the download-threads
        for i in range(len(j["feed"]["entry"])):
            date = j["feed"]["entry"][i]["date"][0]["content"][:10]
            # { uid: { productname, date, cloudcoverage, rastername, coords, level } }
            uid = j["feed"]["entry"][i]["id"]
            product = {}
            product[uid] = {}
            product[uid]["productname"] = j["feed"]["entry"][i]["title"]
            product[uid]["productdate"] = date
            for s in j["feed"]["entry"][i]["str"]:
                if s["name"] == "tileid":
                    product[uid]["tileid"] = s["content"]
                elif s["name"] == "processinglevel":
                    if s["content"] == "Level-1C":
                        product[uid]["processinglevel"] = 1
                    # Level-2Ap stands for 2a pilot-project (https://sentinels.copernicus.eu/web/sentinel/news/-/article/upcoming-sentinel-2-level-2a-product-evolution)
                    elif s["content"] == "Level-2A" or s["content"] == "Level-2Ap":
                        product[uid]["processinglevel"] = 2
                    else:
                        print(
                            "error with content: "
                            + s["content"]
                            + " in product "
                            + product[uid]["productname"]
                        )
                        return
                elif s["name"] == "footprint":
                    product[uid]["footprint"] = s["content"]

            if product[uid]["processinglevel"] == 1:
                # Level 1 data
                try:
                    product[uid]["cloudcoverage"] = float(
                        j["feed"]["entry"][i]["double"]["content"]
                    )
                except TypeError as e:
                    print(
                        "following product: "
                        + product[uid]["productname"]
                        + ", error: "
                        + str(e)
                    )
                    return
            elif product[uid]["processinglevel"] == 2:
                # Level 2 data
                product[uid]["cloudcoverage"] = float(
                    j["feed"]["entry"][i]["double"][0]["content"]
                )
            productList.append(product)

        print(j["feed"]["subtitle"])
        # productList: [ { uid: { ... } }, uid: { ... } }, ...]
        # So a list of one-element-dicts
        for i in range(len(productList)):
            self.dispatcher.addData(productList[i])


class DownloadDispatcher(Dispatcher):
    def initialize(self):
        self.maxThreads = 2
        self.errorcount = 0
        self.errorcountlock = Lock()

    def getWorkerThread(self, data):
        return DownloadWorkerThread(self, data)


# Due to the bad API of the sentinel data, this is quite a mess unfortunately
class DownloadWorkerThread(WorkerThread):
    def run(self):
        # self.data: { uid: { productname, date, cloudcoverage, rastername, coords, level } }
        uid = list(self.data)[0]
        product = self.data[uid]["productname"]
        level = self.data[uid]["processinglevel"]

        # Checks if the uid is already downloaded
        savefilelock.acquire()
        savefile = Path(savefilename)
        if savefile.is_file():
            with open(savefilename, "r") as fr:
                savejson = json.load(fr)
                if uid in savejson:
                    # uid already exists -> cancel download
                    print(
                        uid
                        + " already exists in "
                        + savefilename
                        + " (download canceled)"
                    )
                    savefilelock.release()
                    return
        savefilelock.release()

        # if it is too cloudy, we do not need to download and calculate everything
        if self.data[uid]["cloudcoverage"] < maxcloudcoverage:
            url = (
                "https://scihub.copernicus.eu/dhus/odata/v1/Products('"
                + uid
                + "')/Nodes('"
                + product
                + ".SAFE')/Nodes('"
            )
            # We need to check both files, because of poor data
            try:
                r = requests.get(url + "L2A_Manifest.xml')/$value", auth=(user, pw))
                r.raise_for_status()
            except requests.exceptions.HTTPError:
                r = requests.get(url + "manifest.safe')/$value", auth=(user, pw))
                r.raise_for_status()

            tree = ET.fromstring(r.text)
            for i in range(len(tree[2])):
                href = tree[2][i][0][0].attrib["href"]
                # Here comes Level 1 data
                if level == 1:
                    if "_B04.jp2" in href and level == 1:
                        # watch out, this one is in a 10m raster. Needs to be shrinked before the calculation
                        sclPath = DownloadWorkerThread.extractInformation(href)
                    if "_B8A.jp2" in href and level == 1:
                        sclPath = DownloadWorkerThread.extractInformation(href)

                # Here comes Level 2 data layout
                elif level == 2:
                    if "B04_20m.jp2" in href:
                        b04Path = DownloadWorkerThread.extractInformation(href)
                    if "B8A_20m.jp2" in href:
                        b08Path = DownloadWorkerThread.extractInformation(href)
                    if "SCL_20m.jp2" in href:
                        sclPath = DownloadWorkerThread.extractInformation(href)

            if "b04Path" not in locals():
                # Let's give it a third try, by guessing the folders name -.- (Level 2)
                try:
                    r = requests.get(url + "manifest.safe')/$value", auth=(user, pw))
                    r.raise_for_status()
                    tree = ET.fromstring(r.text)
                    if level == 2:
                        missing1 = (
                            "L2A"
                            + tree[2][10][0][0].attrib["href"][2:].split("/")[1][3:]
                        )
                        # example for missing2: "S2A_MSIL2A_20170825T102021_N0205_R065_T32UPV_20170825T102114"
                        missing2 = "L2A_" + missing1[4:10] + "_" + product[11:26]
                        b04Path = [
                            [
                                "GRANULE",
                                missing1,
                                "IMG_DATA",
                                "R20m",
                                missing2 + "_B04_20m.jp2",
                            ],
                            False,
                        ]
                        b08Path = [
                            [
                                "GRANULE",
                                missing1,
                                "IMG_DATA",
                                "R20m",
                                missing2 + "_B8A_20m.jp2",
                            ],
                            False,
                        ]
                        sclPath = [
                            [
                                "GRANULE",
                                missing1,
                                "IMG_DATA",
                                "R20m",
                                missing2 + "_SCL_20m.jp2",
                            ],
                            False,
                        ]
                    else:
                        missing1 = tree[2][10][0][0].attrib["href"][2:].split("/")[1]
                        # missing2 example: T32UPD_20181101T103151_B8A
                        missing2 = missing1.split("_")[1] + "_" + product.split("_")[2]
                        b04Path = [
                            ["GRANULE", missing1, "IMG_DATA", missing2 + "_B04.jp2"],
                            False,
                        ]
                        b08Path = [
                            ["GRANULE", missing1, "IMG_DATA", missing2 + "_B8A.jp2"],
                            False,
                        ]
                except requests.exceptions.HTTPError as e:
                    # Another try for level 1:
                    print("error: " + str(e))

            try:
                b04Data = DownloadWorkerThread.downloadFile(b04Path, url)
                b08Data = DownloadWorkerThread.downloadFile(b08Path, url)
                d = [self.data, b04Data, b08Data]
                if level == 2:
                    sclData = DownloadWorkerThread.downloadFile(sclPath, url)
                    d.append(sclData)
            except UnboundLocalError as e:
                self.dispatcher.errorcountlock.acquire()
                self.dispatcher.errorcount += 1
                print(
                    "Error: "
                    + str(e)
                    + ", productname: "
                    + str(product)
                    + ", totalerrors: "
                    + str(self.dispatcher.errorcount)
                )
                self.dispatcher.errorcountlock.release()
                return
            self.dispatcher.addData(d)
        else:
            self.dispatcher.addData([self.data])

    """ Second return value indicates whether it has a weird format or not """

    def extractInformation(href):
        if href[0] == "G":
            return [href.split("/"), False]
        if href[0] == "/":
            return [href.split("/"), True]
        else:
            return [href[2:].split("/"), False]

    def downloadFile(path, url):
        url = DownloadWorkerThread.extractDownloadableUrl(url, path)
        r = requests.get(url, stream=True, auth=(user, pw))
        r.raise_for_status()
        with MemoryFile(r.content) as memfile:
            with memfile.open() as dataset:
                data = dataset.read()
        del r
        return data

    def extractDownloadableUrl(url, path):
        for i in range(len(path[0])):
            # path[1] = weirdFormat
            if not path[1] or i > 16:
                url = url + path[0][i] + "')/Nodes('"
        url = url[:-7] + "$value"
        return url


class ComputeDispatcher(Dispatcher):
    def initialize(self):
        self.calculated = 0
        self.notcalculated = 0
        self.calcuLock = Lock()

    def getWorkerThread(self, data):
        return ComputeWorkerThread(self, data)


class ComputeWorkerThread(WorkerThread):
    def run(self):
        # self.data: [ { uid: { productname, date, cloudcoverage, rastername, coords, level } }, b04Data, b08Data, sclData]
        dic = self.data[0]
        uid = list(dic)[0]
        level = dic[uid]["processinglevel"]
        clouds = dic[uid]["cloudcoverage"]

        if clouds < maxcloudcoverage:
            b04Data = self.data[1][0].astype(float)
            b08Data = self.data[2][0].astype(float)
            dic[uid]["calculation"] = {}

            if level == 1:
                # Shrink the b04 data (10m resolution) to 20m resolution
                dsmall = len(b04Data) // 2
                b04Data = b04Data.reshape([dsmall, 2, dsmall, 2]).mean(3).mean(1)

            # num: number of used pixel:
            num = len(b04Data) ** 2 - (b04Data == 0.0).sum()
            numPercent = num / len(b04Data) ** 2
            dic[uid]["calculation"]["usedpercentage"] = numPercent

            # Calculating ndvi
            first = b08Data - b04Data
            second = b08Data + b04Data
            second[second == 0.0] = np.nan
            ndvi = first / second
            ndvimean = np.nanmean(ndvi)
            ndvimedian = np.nanmedian(ndvi)
            ndvistd = np.nanstd(ndvi)
            dic[uid]["calculation"]["ndvimean"] = ndvimean
            dic[uid]["calculation"]["ndvimedian"] = ndvimedian
            dic[uid]["calculation"]["ndvistd"] = ndvistd

            if level == 2:
                dic[uid]["level2data"] = {}
                sclData = self.data[3][0]
                # Calculation vegetation index (percentage of the used pixel, where the scl is == 4)
                vegindex = (sclData == 4).sum() / num
                dic[uid]["level2data"]["vegindex"] = vegindex

                # Only get vegetation (4) and non-vegetation (5) classified pixel
                sclData[sclData == 5] = 4
                second[sclData != 4] = np.nan
                ndvi = first / second
                ndvimean = np.nanmean(ndvi)
                ndvimedian = np.nanmedian(ndvi)
                ndvistd = np.nanstd(ndvi)
                dic[uid]["level2data"]["ndvimean"] = ndvimean
                dic[uid]["level2data"]["ndvimedian"] = ndvimedian
                dic[uid]["level2data"]["ndvistd"] = ndvistd

            self.dispatcher.calcuLock.acquire()
            self.dispatcher.calculated += 1
            print(
                "calculated ("
                + str(self.dispatcher.calculated)
                + "): "
                + dic[uid]["productname"]
                + " (clouds: "
                + str(clouds)
                + ")"
            )
            self.dispatcher.calcuLock.release()
        else:
            self.dispatcher.calcuLock.acquire()
            self.dispatcher.notcalculated += 1
            print(
                "not calculated ("
                + str(self.dispatcher.notcalculated)
                + "): "
                + dic[uid]["productname"]
                + " (clouds: "
                + str(clouds)
                + ")"
            )
            self.dispatcher.calcuLock.release()

        self.dispatcher.addData(dic)

        # Problem: Some areas might have more/better vegetation in general than others. Because of clouds and sheer luck,
        # you might have more pictures of area 1 than of area 2 which could lead to noise in the data. Possible Solutions:
        # 1. Take one Reference-Value and measure the relative change (for example the highest number).
        # 2. Only compare one area to each other (UMD to UMD etc.)
        # 3. Window the data and hope for a good statistic


class SaveDispatcher(Dispatcher):
    def initialize(self):
        self.maxThreads = 1
        self.dict = {}

        # Checks the savefile
        savefilelock.acquire()
        savefile = Path(savefilename)
        if savefile.is_file():
            with open(savefilename, "r") as fr:
                # savejson is here a json
                self.dict = json.load(fr)

        savefilelock.release()

    def getWorkerThread(self, data):
        return SaveWorkerThread(self, data)


class SaveWorkerThread(WorkerThread):
    def run(self):
        #  self.data: [[uid, productname, productdate, cloudcoverage], meanOfNdvi, ndvimeanWithoutChecking, Vegetation]

        self.dispatcher.dict.update(self.data)

        savefilelock.acquire()
        with open(savefilename, "w") as fw:
            json.dump(self.dispatcher.dict, fw)
        savefilelock.release()
