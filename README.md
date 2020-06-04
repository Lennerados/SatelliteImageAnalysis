# Satellite Image Analysis
## Introduction
This is a small framework to analyse satellite images in an efficient manner which was used for a seminar paper. To do that it is using a pipeline architecture which can be found in interfaces.py. Every stage has some inputs and some outputs, which will be fed into the next stage. To add a stage you need to implement the interfaces `WorkerThread`, where you override the method `run` and `Dispatcher`, where you override the method `getWorkerThread`. You can manually add your initial data into the source stage, whereas the sink stage does not have an output. You can also specify the maximum concurrent executions of each stage in the dispatcher. Examples for that are shown in implementations.py. The configuration of a pipeline can be seen in main.py.

## Configfile
The `config.ini` file for the usage of the Satellite Image Analysis system should look like this:

```sh
[DEFAULT]
username = ##userForSentinel##
password = ##pwForSentinel##
querysize = 100
savefilename = ###_v2.json
quandlkey = ##quandlkey##
maxcloudcoverage = 32
```
