import subprocess
import itertools
import argparse
import sys
import os
import time
import random

argparser = argparse.ArgumentParser()
argparser.add_argument('--partition', default='titanx-short:120,m40-short:30', type=str)
argparser.add_argument('--cpu_memory', default='24GB', type=str)
argparser.add_argument('--output_dir', default='hyperparams', type=str)
argparser.add_argument('--script', type=str)

args = argparser.parse_args(sys.argv[1:])

user = os.environ["USER"]
# base_cmd = os.environ["CMD"]
# out_dir = os.environ["OUT_DIR"]

datetime_str = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())

out_dir = os.path.join(args.output_dir, "tune-" + datetime_str)
print("Writing to output dir: %s" % out_dir)

if not os.path.exists(out_dir):
  os.makedirs(out_dir)

# if not base_cmd or not out_dir:
#     print('CMD or OUT_DIR not set')
#     sys.exit(1)

partition_maxjobs = [p.split(':') for p in args.partition.split(',')]
partition_maxjobs = [(s, int(v)) for s, v in partition_maxjobs]

params = {
  'learning_rate': [0.0005, 0.0001, 0.00005, 0.00001],
  'beta1': [0.9],
  'beta2': [0.98, 0.999],
  'epsilon': [1e-12],
  'moving_average_decay': [0.9999],
  'batch_size': [256]
}


def make_job_str(_setting):
    name_setting = {n: _s for n, _s in zip(names, _setting)}
    # setting_list = ['--%s %s' % (name, str(value)) for name, value in name_setting.items()]
    # _setting_str = ' '.join(setting_list)
    setting_list = ["%s=%s" % (name, str(value)) for name, value in name_setting.items()]
    _setting_str = "--hparams %s" % ','.join(setting_list)
    _log_str = '_'.join(map(str, name_setting.values()))
    return _log_str, _setting_str


def add_to_partition(_partition, _setting_str, _log_str):
    slurm_cmd = 'srun --gres=gpu:1 --partition=%s --mem=%s' % (_partition, args.cpu_memory)
    # create dir for this specific job
    log_dir = '%s/%s' % (out_dir, _log_str)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    # write run cmd to file in logdir
    with open('%s/%s' % (log_dir, 'run.cmd'), 'w') as outf:
        outf.write('%s %s\n' % (args.script, _setting_str))
    save_str = "--save_dir %s" % os.path.join(log_dir, "model")
    # create bash cmd which directs into a log
    full_cmd = '%s %s %s %s' % (slurm_cmd, args.script, _setting_str, save_str)
    bash_cmd = '%s &> %s/train.log &' % (full_cmd, log_dir)
    print(bash_cmd)
    subprocess.call(bash_cmd, shell=True)


names, all_params = zip(*[(k, v) for k, v in params.items()])
all_jobs = list(itertools.product(*all_params))
print('Starting %d jobs' % (len(all_jobs)))
random.shuffle(all_jobs)

for setting in all_jobs:
    log_str, setting_str = make_job_str(setting)
    added = False
    while not added:
        for partition, max_jobs in partition_maxjobs:
            # only run max_jobs at once
            running_jobs = int(subprocess.check_output('squeue -u %s -p %s | wc -l'
                                                       % (user, partition), shell=True))
            if running_jobs < max_jobs and not added:
                add_to_partition(partition, setting_str, log_str)
                added = True
            else:
                time.sleep(1)


print('Done. Ran %d jobs.' % len(all_jobs))
