# Satellite Image Analysis
## Introduction
This is a small framework to analyse satellite images in an efficient manner which was used for a seminar paper. To do that it is using a pipeline architecture which can be found in interfaces.py. Every stage has some inputs and some outputs, which will be fed into the next stage. To add a stage you need to implement the interfaces `WorkerThread`, where you override the method `run` and `Dispatcher`, where you override the method `getWorkerThread`. You can manually add your initial data into the source stage, whereas the sink stage does not have an output. You can also specify the maximum concurrent executions of each stage in the dispatcher. Examples for that are shown in implementations.py. The configuration of a pipeline can be seen in `main.py`

## Dependencies
To run the software, you need to install `rasterio`. To install it, simply run `python3 -m pip install rasterio`

## Credentials
The implementations currently use satellite images from the [sentinel project](https://sentinels.copernicus.eu/web/sentinel/home). To access that, you can [register](https://scihub.copernicus.eu/dhus/#/self-registration) for free. You then have to set the environment variables with your credentials: `SENTINEL_USERNAME` must be set to your username and `SENTINEL_PASSWORD` must be set to your password.

## Additional Notes
This software was orignally developed in the year 2018/2019. The API might have changed since then, so I cannot give any guarantee on the current functionality of the software.

Also note, that this was mainly developed as a PoC implementation to automate the workflow, I would have needed to do manually. That's why some features were not added in favor of faster development speed. You should also never use this software for anything related to production.

## Configfile
The `config.ini` file contains information about what data should be downloaded.
