#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 24 11:37:39 2020

@author: worklab
"""


import os,sys,inspect
import numpy as np
import random 
import time
random.seed = 0
import cv2
from PIL import Image
import torch
from torchvision.transforms import functional as F
from torchvision.ops import roi_align
import matplotlib.pyplot  as plt
from scipy.optimize import linear_sum_assignment
import _pickle as pickle


# add all packages and directories to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))))
sys.path.insert(0,parent_dir)

from config.data_paths import directories, data_paths
for item in directories:
    sys.path.insert(0,item)

# filter and CNNs
from _tracker.mp_loader import FrameLoader
from _tracker.torch_kf_dual import Torch_KF
from _localizers.detrac_resnet34_localizer import ResNet34_Localizer
from _detectors.pytorch_retinanet.retinanet.model import resnet50 
from _eval import mot_eval as mot


#%%
result_dir = data_paths["tracking_output"]

# parse all .cpkl files into a single dictionary
# {detector_name:{det_step: results, det_step:results,...},
#  detector_name:{det_step:results,...},
#  ...}

all_results = {
               "ACF":{},
               "CompACT":{},
               "RCNN":{},
               "retinanet":{},
               "retinanet_wer":{},
               "DPM":{},
               "ground_truth":{},
               "kf":{},
               "none":{},
               "skip1":{},
               "apriori":{}
               }



for sub_dir in os.listdir(result_dir):
    if sub_dir in ["retinanet_test","ACF_test","CompACT_test","DPM_test","ground_truth_test","RCNN_test","retinanet_wer_test","kf_test","none_test","skip1_test","apriori_test"]:
        detector = sub_dir.split("_test")[0]
        sub_dir = os.path.join(result_dir,sub_dir)
        
        for file in os.listdir(sub_dir):
            file = os.path.join(sub_dir,file)
            print(file)
            
            try:
                with open(file,"rb") as f:
                    (tracklets,metrics,time_metrics) = pickle.load(f)
            except:
                with open(file,"rb") as f:
                    (tracklets,metrics,time_metrics,_) = pickle.load(f)
    
            # get det_step
            det_step = int(file.split("_")[-1].split(".cpkl")[0])
            track_id = int(file.split("_")[-2])
            
            try:
                all_results[detector][det_step][track_id] = (tracklets,metrics,time_metrics)
            except:
                all_results[detector][det_step] = {track_id:(tracklets,metrics,time_metrics)}
 

#%% Aggregate along all tracks
agg = {}
for key in all_results:
    agg[key] = {}
    for det_step in all_results[key]:
        agg[key][det_step] = {}
        
        n = 0
        aggregator = {}
        for track_id in all_results[key][det_step]:
            # if track_id in [40712,40774,40773,40772,40711,40771,40792,40775,39361,40901]:
                n += 1
                for metric in all_results[key][det_step][track_id][1]:
                    try:
                        aggregator[metric] += all_results[key][det_step][track_id][1][metric][0]
                    except:
                        aggregator[metric] = all_results[key][det_step][track_id][1][metric][0]
        for item in aggregator:
            aggregator[item] = aggregator[item]/n
        agg[key][det_step] = aggregator
        
        # correct ground truth with arbitrary slowdown
        if key == "ground_truth":
            agg[key][det_step]["framerate"] = 1.0/(1.0/ agg[key][det_step]['framerate'] + 0.1* 1/det_step)
        
with open("aggregated_test_results_new.cpkl","wb") as f:
    pickle.dump(agg,f)
            
#%% Generate MOTA-Hz plots for all detectors
# plt.style.use('ggplot')
# with open("/home/worklab/Documents/code/tracking-by-localization/_eval/aggregated_test_results_new.cpkl","rb") as f:
#     agg = pickle.load(f)
    
plot_dict = {
               "ACF":[],
               "CompACT":[],
               "RCNN":[],
               "retinanet":[],
               "retinanet_wer":[],
               "DPM":[],
               "ground_truth":[]
               }

for detector in agg.keys():
    det_steps = []
    detector_hz = []
    detector_MOTAs = []
        
    for det_step in range(50):

        if det_step in agg[detector].keys():
           det_steps.append(det_step)
           detector_hz.append(agg[detector][det_step]["framerate"])
           detector_MOTAs.append(agg[detector][det_step]["mota"])
       
        plot_dict[detector] = (det_steps,detector_hz,detector_MOTAs)

plt.figure()
legend = []
for detector in plot_dict.keys():
    legend.append(detector)
    a,b,c = plot_dict[detector]
    plt.plot(b,c,linewidth = 3)

plt.legend(legend,fontsize = 20)
plt.tick_params(axis='x', labelsize= 16)
plt.tick_params(axis='y', labelsize= 16)
plt.xlabel("Framerate (Hz)",fontsize = 20)
plt.ylabel("Accuracy(MOTA)",fontsize = 20)
    
#%% Generate relative MOTA-Hz plots for all detectors
with open("aggregated_test_results.cpkl","rb") as f:
    agg = pickle.load(f)
    
plot_dict = {
               "ACF":[],
               "CompACT":[],
               "RCNN":[],
               "retinanet":[],
               "DPM":[],
               "ground_truth":[]
               }

for detector in agg.keys():
    det_steps = []
    detector_hz = []
    detector_MOTAs = []
        
    for det_step in range(50):
        if det_step == 1:
            baseline_hz = agg[detector][det_step]["framerate"]
            baseline_mota = agg[detector][det_step]["mota"]
        if det_step in agg[detector].keys():
           det_steps.append(det_step)
           detector_hz.append(agg[detector][det_step]["framerate"]/baseline_hz)
           detector_MOTAs.append(agg[detector][det_step]["mota"]/baseline_mota)
       
        plot_dict[detector] = (det_steps,detector_hz,detector_MOTAs)

plt.figure()
legend = []
for detector in plot_dict.keys():
    legend.append(detector)
    a,b,c = plot_dict[detector]
    plt.plot(b,c,linewidth = 3)

plt.legend(legend,fontsize = 20)
plt.tick_params(axis='x', labelsize= 16)
plt.tick_params(axis='y', labelsize= 16)
plt.xlabel("Relative framerate",fontsize = 20)
plt.ylabel("Relative accuracy",fontsize = 20)
 
       
#%% Plot time metrics for retinanet
all_time_metrics = {}
for det_step in all_results["retinanet"]:
    time_metrics = {}

    for track_id in all_results["retinanet"][det_step]:
        for key in all_results['retinanet'][det_step][track_id][2].keys():
            try:
                time_metrics[key] += all_results['retinanet'][det_step][track_id][2][key]
            except:
                time_metrics[key] = all_results['retinanet'][det_step][track_id][2][key]
    all_time_metrics[det_step] = time_metrics
    
max_time = sum(all_time_metrics[1][key] for key in all_time_metrics[1].keys() )
time_agg = {}
det_steps = []
for key in all_time_metrics[1].keys():
    time_agg[key] = []
for det_step in range(50):
    if det_step in all_time_metrics.keys():
        det_steps.append(det_step)
        for key in all_time_metrics[det_step].keys():
            time_agg[key].append(all_time_metrics[det_step][key]/max_time)

time_agg["filter and manage tracks"] = [time_agg["predict"][i] + time_agg["update"][i] + time_agg["add and remove"][i] + time_agg["store"][i] + time_agg["plot"][i] for i in range(len(time_agg["update"]))]
time_agg["detect"] = [time_agg["detect"][i] + time_agg["parse"][i] + time_agg["load"][i] for i in range(len(time_agg["detect"]))]
time_agg["localize"] = [time_agg["localize"][i] + time_agg["pre_localize and align"][i] + time_agg["post_localize"][i] for i in range(len(time_agg["localize"]))]

del time_agg["predict"]
del time_agg["update"]
del time_agg["parse"]
del time_agg["add and remove"]
del time_agg["store"]
del time_agg["plot"]
del time_agg["pre_localize and align"]
del time_agg["post_localize"]
del time_agg["load"]

plots  = [time_agg[key] for key in time_agg.keys()]
legend = [key for key in time_agg.keys()]
legend = [legend[1],legend[2],legend[3],legend[0]]
plots  = [plots[1],plots[2],plots[3],plots[0]]

plt.stackplot(det_steps,plots)
plt.legend(legend,fontsize = 18)
plt.xlabel("Frames between detection",fontsize = 20)
plt.ylabel("Relative Time Utilization",fontsize = 20)
plt.xlim([0,45])
plt.ylim([0,1])

# combine predict and update
# combine detect and parse
# combine add and remove and store
# combine pre, localize, and post
# remove plot
# divide by total



#%% Compute MOTA at a variety of IOU requirements
track_dir = data_paths["test_im"]
label_dir = data_paths["test_lab"]
track_list = [os.path.join(track_dir,item) for item in os.listdir(track_dir)]  
label_list = [os.path.join(label_dir,item) for item in os.listdir(label_dir)]
track_dict = {}
for item in track_list:
    id = int(item.split("MVI_")[-1])
    track_dict[id] = {"frames": item,                     "labels": None}
for item in label_list:
    id = int(item.split("MVI_")[-1].split(".xml")[0])
    track_dict[id]['labels'] = item
    
    
# for indexing all_results
track_keys = list(track_dict.keys())
det_steps = [1,3,5,9,15,21,29,35,45]
iou_reqs = [0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0]

# for storing all results
all_results = np.zeros([len(track_keys),len(det_steps),len(iou_reqs)])
all_APs = np.zeros([len(track_keys),len(det_steps),len(iou_reqs)])
all_ARs = np.zeros([len(track_keys),len(det_steps),len(iou_reqs)])
result_dir = data_paths["tracking_output"]

# iterate through tracks
for i in range(len(track_keys)):
    
    # load ground truths for this track
    id = track_keys[i]
    gts,metadata = mot.parse_labels(track_dict[id]["labels"])
    ignored_regions = metadata['ignored_regions']
    
    # iterate through det_steps
    for j in range(len(det_steps)):
        det_step = det_steps[j]
        
        # get detections
        file = os.path.join(result_dir,"retinanet_test","results_{}_{}.cpkl".format(id,det_step))
        try:
            with open(file,"rb") as f:
                (tracklets,metrics,time_metrics) = pickle.load(f)
        except:
            with open(file,"rb") as f:
                (tracklets,metrics,time_metrics,_) = pickle.load(f)
                
        # iterate through IOU requirements
        for k in range(len(iou_reqs)):
            metrics,acc = mot.evaluate_mot(tracklets,gts,ignored_regions,threshold = iou_reqs[k],ignore_threshold = 0.2)
            metrics = metrics.to_dict()
            all_results[i,j,k] = metrics["mota"][0] 
            all_APs[i,j,k] = metrics["precision"][0] 
            all_ARs[i,j,k] = metrics["recall"][0] 
            print("Result for track {}, det step {}, threshold {}: {}, {} ,{}".format(id,det_step,iou_reqs[k],all_results[i,j,k],all_APs[i,j,k],all_ARs[i,j,k]))
            
with open("multiple_threshold_results.cpkl","wb") as f:
    pickle.dump((all_results,all_APs,all_ARs),f)
    
#%% Plot various IOUs
plt.style.use('default')

with open("/home/worklab/Documents/code/tracking-by-localization/_eval/multiple_threshold_results.cpkl","rb") as f:
    all_results,all_APs,all_ARs = pickle.load(f)

colors = np.zeros([12,3])
for i in range(len(colors)):
    colors[i] = np.array([0.1,1,0.2]) + i/12* np.array([0.8,-1,0])
colors = colors[::-1,:]  
legend = [np.round(1-i,1) for i in iou_reqs]

means = np.mean(all_results,axis = 0)
means = np.transpose(means)
plt.figure(figsize = (3,6))
for j,row in enumerate(means):
    plt.plot(det_steps,row,color = colors[j])
#plt.legend(legend, title = "Minimum IoU for Match")
plt.xlabel("Frames Between Detection",fontsize = 20)
plt.ylabel("MOTA",fontsize = 20)
    


means = np.mean(all_APs,axis = 0)
means = np.transpose(means)
plt.figure(figsize = (3,6))
for j,row in enumerate(means):
    plt.plot(det_steps,row,color = colors[j])
#plt.legend(legend, title = "Minimum IoU for Match")
plt.xlabel("Frames Between Detection",fontsize = 20)
plt.ylabel("Precision",fontsize = 20)


means = np.mean(all_ARs,axis = 0)
means = np.transpose(means)
plt.figure(figsize = (3,6))
for j,row in enumerate(means):
    plt.plot(det_steps,row,color = colors[j])
plt.legend(legend, title = "Minimum IoU for Match")
plt.xlabel("Frames Between Detection",fontsize = 20)
plt.ylabel("Recall",fontsize = 20)
plt.xlim([0,200])
#%% Plot various IOUs other orientation
plt.style.use('default')

with open("/home/worklab/Documents/code/tracking-by-localization/_eval/multiple_threshold_results.cpkl","rb") as f:
    all_results,all_APs,all_ARs = pickle.load(f)

colors = np.zeros([10,3])
for i in range(len(colors)):
    colors[i] = np.array([.2,.2,1]) + i/10* np.array([.8,0,-0.8])
colors[0] = np.array([0.8,0.8,0.1])

iou_reqs = [1-i for i in iou_reqs]
legend = [i for i in det_steps]
means = np.mean(all_results,axis = 0)
plt.figure()
for j,row in enumerate(means):
    plt.plot(iou_reqs,row,color = colors[j])
#plt.legend(legend, title = "d")
plt.xlabel("Required iou for match",fontsize = 20)
plt.ylabel("MOTA",fontsize = 20)
    

legend = [i for i in det_steps]
means = np.mean(all_APs,axis = 0)
plt.figure()
for j,row in enumerate(means):
    plt.plot(iou_reqs,row,color = colors[j])
#plt.legend(legend, title = "d")
plt.xlabel("Required iou for match",fontsize = 20)
plt.ylabel("Precision",fontsize = 20)

legend = [i for i in det_steps]
means = np.mean(all_ARs,axis = 0)
plt.figure()
for j,row in enumerate(means):
    plt.plot(iou_reqs,row,color = colors[j])
#plt.legend(legend, title = "d")
plt.xlabel("Required iou for match",fontsize = 20)
plt.ylabel("Recall",fontsize = 20)




#%% Get metrics for other fast tracking methods
result_dir = data_paths["tracking_output"]

# parse all .cpkl files into a single dictionary
# {detector_name:{det_step: results, det_step:results,...},
#  detector_name:{det_step:results,...},
#  ...}

all_results = {
               "none":{},
               "kf":{},
               "kf_loc":{}    
               }


for sub_dir in os.listdir(result_dir):
    if sub_dir in ["none","kf","kf_loc"]:
        detector = sub_dir
        sub_dir = os.path.join(result_dir,sub_dir)
        
        for file in os.listdir(sub_dir):
            file = os.path.join(sub_dir,file)
            print(file)
            
            try:
                with open(file,"rb") as f:
                    (tracklets,metrics,time_metrics) = pickle.load(f)
            except:
                with open(file,"rb") as f:
                    (tracklets,metrics,time_metrics,_) = pickle.load(f)
    
            # get det_step
            det_step = int(file.split("_")[-1].split(".cpkl")[0])
            track_id = int(file.split("_")[-2])
            
            try:
                all_results[detector][det_step][track_id] = (tracklets,metrics,time_metrics)
            except:
                all_results[detector][det_step] = {track_id:(tracklets,metrics,time_metrics)}
with open ("alternate_results.cpkl","wb") as f:
     pickle.dump(all_results,f)
     
#%% Aggregate along all tracks
agg = {}
for key in all_results:
    agg[key] = {}
    for det_step in all_results[key]:
        agg[key][det_step] = {}
        
        n = 0
        aggregator = {}
        for track_id in all_results[key][det_step]:
            # if track_id in [40712,40774,40773,40772,40711,40771,40792,40775,39361,40901]:
                n += 1
                for metric in all_results[key][det_step][track_id][1]:
                    try:
                        aggregator[metric] += all_results[key][det_step][track_id][1][metric][0]
                    except:
                        aggregator[metric] = all_results[key][det_step][track_id][1][metric][0]
        for item in aggregator:
            aggregator[item] = aggregator[item]/n
        agg[key][det_step] = aggregator
        
        # correct ground truth with arbitrary slowdown
        if key == "ground_truth":
            agg[key][det_step]["framerate"] = 1.0/(1.0/ agg[key][det_step]['framerate'] + 0.1* 1/det_step)
        
        # with open("aggregated_test_results.cpkl","wb") as f:
        #     pickle.dump(agg,f)
            
#%% Generate relative MOTA-Hz plots for all detectors
 with open("/home/worklab/Documents/code/tracking-by-localization/_eval/aggregated_test_results.cpkl","rb") as f:
     agg2 = pickle.load(f)
agg["retinanet"] = agg2["retinanet"]    

plot_dict = {
               "kf_only":[],
               "no_kf":[],
               "none":[]
               }

for detector in agg.keys():
    det_steps = []
    detector_hz = []
    detector_MOTAs = []
        
    for det_step in range(50):
        if det_step == 1:
            baseline_hz = 1#agg[detector][det_step]["framerate"]
            baseline_mota = 1# agg[detector][det_step]["mota"]
        if det_step in agg[detector].keys():
           det_steps.append(det_step)
           detector_hz.append(agg[detector][det_step]["framerate"]/baseline_hz)
           detector_MOTAs.append(agg[detector][det_step]["mota"]/baseline_mota)
       
        plot_dict[detector] = (det_steps,detector_hz,detector_MOTAs)

plt.figure()
legend = []
for detector in plot_dict.keys():
    legend.append(detector)
    a,b,c = plot_dict[detector]
    plt.plot(b,c,linewidth = 3)

plt.legend(legend,fontsize = 20)
plt.tick_params(axis='x', labelsize= 16)
plt.tick_params(axis='y', labelsize= 16)
plt.xlabel("Relative framerate",fontsize = 20)
plt.ylabel("Relative accuracy",fontsize = 20)