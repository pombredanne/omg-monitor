# Swarming for parameters

With NuPIC we can [swarm] the space of parameters to find better models. I will keep here the files I used to swarm the parameters currently used. You can see the parameters in the file [../monitor/model_params_monitor.py].

## Instructions

* First we must create a sample dataset in which do the swarm. This is done with the [create_dateset.py] file. We must call it from the root directory and we have to pass our Pingdom credentials plus a check id as parameters.

* Then we need to generate the files `permutations.py` and `description.py`, as we will change it to use a Random Distributed Scalar Encoder for the response time. You can use the files already generated, or you could do this by running the following command, then copying the file `description.py` and `permutations.py` to this directory. 
```
$NUPIC/build/release/lib/python2.7/site-packages/nupic/frameworks/opf/exp_generator/ExpGenerator.py --descriptionFromFile='swarm/search_def.json'
```

* We change the `permutations.py` file by replacing the responsetime specification for this one:
```
  u'responsetime': PermuteEncoder(fieldName='responsetime', seed=1, encoderClass='RandomDistributedScalarEncoder', resolution=PermuteInt(10, 400), ),
```

* We change the `description.py` file by replacing the responsetime specification for this one:
```
  u'responsetime':     { 
    'fieldname': u'responsetime',
    'resolution': 10,
    'name': u'responsetime',
    'type': 'RandomDistributedScalarEncoder'
        },
```

* We run the swarm from the swarm directory:
```
$NUPIC/bin/run_swarm permutations.py --maxWorkers=4
```

* We copy the `model_0/model_params.py` file and replace the old one:
```
cp model_0/model_params.py` ../monitor/model_params_monitor.py
```

[swarm]:https://github.com/numenta/nupic/wiki/Running-Swarms
[../monitor/model_params_monitor.py]:../monitor/model_params_monitor.py
[create_dateset.py]:create_dateset.py