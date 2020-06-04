#!/usr/bin/py

from implementation import *
from util import Util

def main():
    # Input 
    # Small part of Germany
    coords = [[11.86, 51.846], [11.871, 52.716], [7.833, 52.536], [7.927, 51.464], [11.937, 51.361], [11.86, 51.846]]
    from_date = date(2016, 12, 1)
    till_date = date.today()
    max_cloud_coverage = 100.0
    query  = [coords, from_date, till_date, max_cloud_coverage]
    Util.checkQuery(query)

    # Initialize the components
    source = Source()
    countDispatcher = CountDispatcher()
    queryDispatcher = QueryDispatcher()
    downloadDispatcher = DownloadDispatcher()
    computeDispatcher = ComputeDispatcher()
    saveDispatcher = SaveDispatcher()

    # Connect everything
    countDispatcher.connect(source)
    countDispatcher.connect(queryDispatcher)
    queryDispatcher.connect(downloadDispatcher)
    downloadDispatcher.connect(computeDispatcher)
    computeDispatcher.connect(saveDispatcher)

    # Finish the pipeline
    source.finish()

    # Load the data
    source.addData(query, True)

    # Start the execution
    print("Let's start!")
    source.start()

if __name__ == '__main__':
    main()
