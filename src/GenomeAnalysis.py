#!/usr/bin/python

import sys
import os
import re
from collections import defaultdict
import operator
import shutil
import ConfigParser
from os import listdir
from os.path import isfile, join
from data_manager import  calculateNWindowedDistances

number_of_arguments = len(sys.argv)
if number_of_arguments != 5: #Or all parameters, or no parameters 
    print "Not enought parameters. Config_file, subset, std_dev and cut_off_percentage are required."
    print " -config_file: file with more data. Check config_template.ini for an example"
    print " -subet: number of best models you want to retrieve from all models"
    print " -std_dev: in Angstroms. Freedom in Angstroms that is given to a restraint so it is considered as fulfilled restraint. For example: 1000 if max_distance is 10000"
    print " -cut_off_percentage: Maximum percentage of not fulfilled restraints that will be allowed to take as a good model. For example: 15"

    sys.exit()
if len(sys.argv) > 1:  #if we pass the arguments (in the cluster)
    ini_file = sys.argv[1]
    subset = int(sys.argv[2])
    std_dev = int(sys.argv[3])
    cut_off_percentage = int(sys.argv[4])

#read the config file
config = ConfigParser.ConfigParser()
try:
    config.read(ini_file)
    verbose = config.get("ModelingValues", "verbose")
    prefix = config.get("ModelingValues", "prefix")
    fragments_in_each_bead = float(config.get("ModelingValues", "fragments_in_each_bead"))
    uZ = float(config.get("ModelingValues", "max_zscore"))
    lZ = float(config.get("ModelingValues", "min_zscore"))
    y2 = int(config.get("ModelingValues", "max_dist"))
    data_dir = config.get("ModelingValues", "data_dir")
    file_names = config.get("ModelingValues", "file_names")
    file_names = re.sub('[\n\s\t]','',file_names)
    file_names = file_names.split(",")
    files = [data_dir+f for f in file_names]
    viewpoint_fragments = config.get("ModelingValues", "viewpoint_fragments")
    viewpoint_fragments = re.sub('[\n\s\t]','',viewpoint_fragments)
    viewpoint_fragments = viewpoint_fragments.split(",")
    viewpoint_fragments = [ int(i) for i in viewpoint_fragments]
    viewpoint_fragments = [int(i/fragments_in_each_bead) for i in viewpoint_fragments]
    number_of_fragments = int(config.get("ModelingValues", "number_of_fragments"))
    number_of_fragments = int(number_of_fragments/fragments_in_each_bead)
    working_dir = config.get("ModelingValues", "working_dir")
    number_of_models = int(config.get("ModelingValues", "number_of_models"))
    jump = number_of_models
except:
    print "\nError reading the configuration file.\n"
    print sys.exc_info()[1]
    sys.exit()

root = "{}data/{}/{}_output_{}_{}_{}/".format(working_dir,prefix,prefix,uZ,lZ,y2)
score_file = "{}/score.txt".format(root)
if verbose == "True":
    def verboseprint(text):
        print text;
else:
    verboseprint = lambda *a: None      # do-nothing function




pyfiles = [ f for f in listdir(root) if isfile(join(root,f)) and f.endswith(".py") ]
number_of_models = len(pyfiles)
try:
    os.remove(root+"score.txt")
except OSError:
    pass
scorefiles = [ f for f in listdir(root) if isfile(join(root,f)) and f.startswith("score") ]
number_of_score_files = len(scorefiles)

models = defaultdict(list) # dict: each model ahs a list of 2 values

# first we create a unified score.txt
with open (score_file,"w") as f:
    counter = 0
    for i in range(number_of_score_files):
        with open (root+"score"+str(counter)+".txt", "r") as f2:
            for line in f2:
                f.write(line)
        counter = counter + jump
        
# create the dictionary and populate it
with open (score_file, "r") as f:
    counter = 0
    for line in f:
        counter += 1
        model = []
        values = re.split("\t", line)
        number = int(values[0])
        score = float(values[1])
        model.append(score)
        models[number] = model
        if counter == number_of_models:
            break

# models = models[:number_of_models]    #take aonly the first ones 
        
reads_values,reads_weights,start_windows, end_windows = calculateNWindowedDistances(int(fragments_in_each_bead),uZ,lZ, y2,files)


print "getting best {} models\n".format(subset)
analized_models = 0
ok_models = 0
for i in range(number_of_models):
    distances_in_model = []
    with open (root+prefix+str(i)+".txt","r") as f:
        for line in f:
            value = re.split("\t",line)
            distances_in_model.append(value)
#         print distances_in_model
    #EVALUATION
 
 
    not_fulfilled = 0
    total = 0
    for k in range(len(files)):

        values = reads_values[k] 
        for j in range(number_of_fragments):
            if j != viewpoint_fragments[k]:
                
                real_d = distances_in_model[k][j]
                 
                should_be_d = values[j] 
                if should_be_d != 0:
                    total += 1
                    if (should_be_d + std_dev < float(real_d)  or should_be_d - std_dev > float(real_d)):
                        not_fulfilled += 1
            #             print "restraint "+str(j)+"not fulfilled"
                        
                        verboseprint ("Restraint " +str(j)+"-"+str(viewpoint_fragments[k])+" is "+str(real_d)+" and should be "+str(should_be_d)+" +- "+str(std_dev)+". Difference: "+str(should_be_d-float(real_d)))
#     print str(i)+"-> Not fulfilled restraints: "+str(not_fulfilled)+"/"+str(total),"%",str(not_fulfilled*100/(total))     
    fulfil_percentage = not_fulfilled*100/total
    print "not_fulfilled -> {} out of {} restraints: {}% of all restraints are not fulfilled in this model.".format(not_fulfilled,total,fulfil_percentage)
    if fulfil_percentage <= cut_off_percentage:
        models[i].append(not_fulfilled)
        ok_models += 1
    else:
        try:
            del models[i]
        except:
            print "Not enough models for the analysis. Try changing the parameters in the config file for 'std_dev' or 'cut_off_percentage'."
    analized_models += 1
    print "Percentage of models that fulfill the threshold: {}%".format(100*ok_models/analized_models)
    print "{}/{}".format(ok_models,analized_models)
    #print "{} -> number of models in subset {}".format(i,len(models))  
# after poplating all and takign out the models out of the cout off, take the subset of models



#order the dictionary by score
sorted_models = sorted(models.items(), key=operator.itemgetter(1))
print "\nNumber of models below cutoff: {}".format(len(sorted_models))

# store them in a folder
storage_folder = working_dir+"data/"+prefix+"/"+prefix+"_final_output_"+str(uZ)+"_"+str(lZ)+"_"+str(y2)+"/" #the dir where the data will be saved
print "copying best {} models to {}".format(subset,storage_folder)
if not os.path.exists(storage_folder): os.makedirs(storage_folder)   

models_subset = sorted_models [:subset]
for k in range(subset):
    
    i = models_subset[k][0]
    shutil.copyfile("{}{}{}.py".format(root,prefix,i), "{}{}{}.py".format(storage_folder,prefix,i) )
    shutil.copyfile("{}{}{}.txt".format(root,prefix,i), "{}{}{}.txt".format(storage_folder,prefix,i) )



# create the file to open in chimera
# superposition of the best models
with open(working_dir+"data/"+prefix+"_superposition.py","w") as f:
    f.write("import os\nfrom chimera import runCommand as rc\nfrom chimera import replyobj\nos.chdir(\""+root+"\")\n")
    f.write("rc(\"open {}{}.py\")\n".format(prefix,models_subset[0][0]))
    for k in range(1,subset):
        i = models_subset[k][0]
#         print("rc(\"open {}{}.py\")\n".format(prefix,i))
#         print("rc(\"match #{}-{} #0-{}\")\n".format((k+1)*number_of_fragments,(k+1)*number_of_fragments+number_of_fragments-1,number_of_fragments-1))
        f.write("rc(\"open {}{}.py\")\n".format(prefix,i))
        f.write("rc(\"match #{}-{} #0-{}\")\n".format(k*number_of_fragments,k*number_of_fragments+number_of_fragments-1,number_of_fragments-1))

print "Superposition of {} models created in {}data/{}\n".format(subset,working_dir,prefix)

print "Now run 'python src/GenomeClustering.py {} {} 2'".format(ini_file,subset)
