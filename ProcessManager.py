# -----------------------------------------------------------------------------
# ProcessManager.py coordinates the worker processes for the global model
# -----------------------------------------------------------------------------

import multiprocessing
import math 
import random
import pickle
import os
import time
import gc
from datetime import datetime  
from datetime import timedelta  

import Region
import WorkerProcess
import Utils
import ParameterSet


def BuildGlobalPopulations(GlobalLocations,GlobalInteractionMatrix,modelPopNames,HospitalTransitionRate,PopulationParameters,DiseaseParameters,SimEndDate,numregions=0,multiprocess=True):
    num_regions = multiprocessing.cpu_count() * 2
    
    
    if numregions > 0:
        num_regions = numregions
    n = math.ceil(len(GlobalLocations) / num_regions)
    
    # Break the global locations list and interaction matrix into separate regional lists
    RegionInteractionMatrixList = []
    RegionalLocations = []
    RegionalList = []
    RegionListGuide = []
    HospitalTransitionMatrix = []
    for i in range(0,(len(GlobalLocations) + n - 1) // n ):
        RegionInteractionMatrixList.append(GlobalInteractionMatrix[i * n:(i + 1) * n,:])
        RegionalLocations.append(GlobalLocations[i * n:(i + 1) * n])
        if(len(HospitalTransitionRate) == len(GlobalInteractionMatrix)):
            HospitalTransitionMatrix.append(HospitalTransitionRate[i * n:(i + 1) * n,:])   
        RegionalList.append(i)
        numInList = (i + 1) * n - i * n
        for R in range(0,numInList):
            RegionListGuide.append(i)
            
    numInfList = {}
    
    
    if multiprocess:
        if(len(HospitalTransitionRate) == len(GlobalInteractionMatrix)):
            jobs = [ multiprocessing.Process(target=WorkerProcess.BuildPops, args=[i,PopulationParameters,DiseaseParameters,SimEndDate,RegionalLocations[i],RegionInteractionMatrixList[i],RegionListGuide,modelPopNames,HospitalTransitionMatrix[i]]) for i in range(0,len(RegionalList)) ]
        else:
            jobs = [ multiprocessing.Process(target=WorkerProcess.BuildPops, args=[i,PopulationParameters,DiseaseParameters,SimEndDate,RegionalLocations[i],RegionInteractionMatrixList[i],RegionListGuide,modelPopNames]) for i in range(0,len(RegionalList)) ]
        
        for j in jobs:
            j.start()
        	
        for j in jobs:
            j.join()
        
        #print("finished creating pops")
        
        for i in range(0,len(RegionalList)):
            regionStats = Utils.FileRead(ParameterSet.PopDataFolder + "/" + str(modelPopNames) + str(i) + "STATS.pickle")
            numInfList[i] = regionStats
        
        return RegionalList, numInfList, RegionListGuide
    else:
        Regions = []
        for i in range(0,len(RegionalList)):
            if(len(HospitalTransitionRate) == len(GlobalInteractionMatrix)):
                region = Region.Region(RegionalLocations[i], RegionInteractionMatrixList[i], i, RegionListGuide,HospitalTransitionMatrix[i],PopulationParameters,DiseaseParameters,SimEndDate)
            else:
                HospitalTransitionMatrix=[]
                region = Region.Region(RegionalLocations[i], RegionInteractionMatrixList[i], i, RegionListGuide,HospitalTransitionMatrix,PopulationParameters,DiseaseParameters,SimEndDate)
            numInfList[i] = region.getRegionStats() 
            Regions.append(region)
        return RegionalList, numInfList, RegionListGuide, Regions    
        
def AllPopsExist(RegionalList,modelPopNames):
    for i in range(0,len(RegionalList)):
        if not os.path.exists(ParameterSet.PopDataFolder + "/" + str(modelPopNames) + str(i) + ".pickle"):
            return False
    return True        


    
def RunFullModel(RegionalList,PopulationParameters,DiseaseParameters,simLength,stepLength,modelPopNames,resultsName,numInfList, randomInfect,LocationImportationRisk=[],RegionListGuide=[],multiprocess=True,Regions=[]):

    totInf = 0
    totC = 0
    totH = 0
    totN = 0
    totR = 0
    totS = 0
    totD = 0
    for key in numInfList.keys():
        rdict = numInfList[key]
        for rkey in rdict:
            lpdict = rdict[rkey]
            if len(lpdict) > 0:
                totInf += lpdict['I']
                totC += lpdict['C']
                totH += lpdict['H']
                totN += lpdict['N']
                totR += lpdict['R']
                totS += lpdict['S']
                totD += lpdict['D']
            
    if(ParameterSet.debugmodelevel >= ParameterSet.debugnotice):
        print("num:", totS+totN+totInf+totC+totR+totD," numS:",totS," numN:",totN," NumInf:",totInf," NumC:",totC," numR:",totR," numD:",totD," numH:",totH)
    totvalue = totS+totN+totInf+totC+totR+totD
    
    timeNow = 0
    timeRange = []
    
    while timeNow < simLength:
        timeNow = timeNow + stepLength
        timeRange.append(timeNow)

    results = {}
    aggregatedresults = {}

    CurrentHospOccList = {}
    resultsNonMP = {}
    ### data for reconciliation
    offPopQueueEvents = []
    RegionReconciliationEvents = {} 
    testRegionValues = {}     
    for i in range(0,len(RegionalList)):
        RegionReconciliationEvents[i] = []
    
    nextEventTimeList = []
    for i in range(0,len(RegionalList)):
        nextEventTimeList.append(0)    
        
    for tend in timeRange:
        
        
        # Infect Random Agents - linear increase in number infected
        infect = [0]*len(RegionalList)
        LPIDinfect = -1
        if randomInfect:
            if len(LocationImportationRisk) > 0:
                LPIDinfect = Utils.multinomial(LocationImportationRisk,sum(LocationImportationRisk))
                rnum = RegionListGuide[LPIDinfect]
            else:
                rnum = random.choice(RegionalList)
            infect[rnum] = DiseaseParameters['ImportationRate']
            nextEventTimeList[rnum] = 0
        if ParameterSet.ModelRunning == 'Wuhan':
            if tend == 1:
                infect = [numStartingInfections]*len(RegionalList)
        
        
        nextEventTime = {}
        offPopQueueEvents = []
        R0Stats = [0]*101
        if multiprocess:
            jobs = []
            for i in range(0,len(RegionalList)):
                #if nextEventTimeList[i] <= tend:
                 jobs.append(multiprocessing.Process(target=WorkerProcess.RunTimeForward,
                                                        args=(i,PopulationParameters,DiseaseParameters,tend,
                                                              modelPopNames,RegionReconciliationEvents[i],infect[i],LPIDinfect)))
            
            for j in jobs:
                j.start()
            	
            for j in jobs:  
                j.join()
            
            for i in range(0,len(RegionalList)):
                numinfVals = Utils.FileRead(ParameterSet.PopDataFolder + "/" + str(modelPopNames) + str(i) + "RegionStats.pickle")
                for key in numinfVals.keys():
                    numInfList[key] = numinfVals[key]
                
                testRegionValues[i] = 0
                RegionReconciliationEvents[i] = []
                try:
                    OPQE = Utils.FileRead(ParameterSet.QueueFolder+"/"+str(modelPopNames)+str(i)+"Queue.pickle")
                except:
                   OPQE = None 
                if OPQE:
                    offPopQueueEvents.extend(OPQE)
                try:
                    os.remove(ParameterSet.QueueFolder+"/"+str(modelPopNames)+str(i)+"Queue.pickle")
                except:
                    if(ParameterSet.debugmodelevel >= ParameterSet.debugnotimportant): print("ProcessManager:ReconcileEventsProcess():File Not Found for Removal: Queues/"+str(modelPopNames)+str(i)+"Queue.pickle")
                    
                if os.path.exists(ParameterSet.PopDataFolder + "/" + str(modelPopNames) + str(i) + "R0Stats.pickle"):
                    R0StatsList = Utils.FileRead(ParameterSet.PopDataFolder + "/" + str(modelPopNames) + str(i) + "R0Stats.pickle")
                    for key in R0StatsList.keys():
                        R0Stat = R0StatsList[key]
                        for rkey in R0Stat.keys():
                            rvals = R0Stat[rkey]
                            for r in range(0,len(rvals)):
                                R0Stats[r] += rvals[r]
        else:
            for i in range(0,len(RegionalList)):
                numEvents,saveRegion, regionStatsX,R,OPQE,hospOccupancyList,R0StatsList,AgeStatsList = \
                                WorkerProcess.RunRegionForward(i,PopulationParameters,DiseaseParameters,Regions[i],tend,
                                          modelPopNames,RegionReconciliationEvents[i],infect[i],LPIDinfect)                        
                
                CurrentHospOccList[tend] = hospOccupancyList
                numinfVals = regionStatsX
                testRegionValues[i] = 0
                for key in numinfVals.keys():
                    numInfList[key] = numinfVals[key]
                if OPQE:
                    offPopQueueEvents.extend(OPQE)     
    
                for key in R0StatsList.keys():
                    R0Stat = R0StatsList[key]
                    for rkey in R0Stat.keys():
                        rvals = R0Stat[rkey]
                        for r in range(0,len(rvals)):
                            R0Stats[r] += rvals[r]
                                
        totInf = 0
        totC = 0
        totH = 0
        totN = 0
        totR = 0
        totD = 0
        totS = 0
        totHI = 0
        totHE = 0
        x = 0
        totICU = 0
        for key in numInfList.keys():
            rdict = numInfList[key]
            for rkey in rdict:
                lpdict = rdict[rkey]
                if len(lpdict) > 0:
                    totInf += lpdict['I']
                    totC += lpdict['C']
                    totH += lpdict['H']
                    totICU += lpdict['ICU']
                    totN += lpdict['N']
                    totR += lpdict['R']
                    totD += lpdict['D']
                    totS += lpdict['S']
                    totHI += lpdict['HI']
                    totHE += lpdict['HE']
        
        if totS+totN+totInf+totC+totR+totD != totvalue:
            print("Error - something went wrong with the data -- please fix. This can only happen if there is a bug in the code")
            exit()
            
        ## Sort them by region            
        for QE in offPopQueueEvents:
            #ts = QE.getEventTime()
            Rid = QE.getRegionId()
            testRegionValues[Rid]+=1
            RegionReconciliationEvents[Rid].append(QE)

        if(ParameterSet.debugmodelevel >= ParameterSet.debugnotice):
            if ParameterSet.ModelRunning == 'Wuhan':
                x = datetime(2020, 1, 23) - timedelta(days=timeRange[len(timeRange)-1]-tend) 
            elif ParameterSet.ModelRunning == 'MarylandFit':
                x = datetime(2020, 4, 1) - timedelta(days=timeRange[len(timeRange)-1]-tend) 
            else:          
                x = datetime(2020, 2, 8) + timedelta(days=tend) 
            
            #print("End:",tend," (",(x.strftime('%Y-%m-%d')),") Time:",t3-t1,"(",t3-t2,") num:", totS+totN+totInf+totC+totR+totD," numS:",totS," numN:",totN," NumInf:",totInf," NumC:",totC," numR:",totR," numD:",totD," numH:",totH," R0:",round(R0,2)," R0R:",round(R0R,2)," R0HH:",round(R0HH,2)," HI:",totHI," HE:",totHE)
            
            
            rnum = 0
            rdenom = 0
            for i in range(1,len(R0Stats)):
                rdenom += R0Stats[i]
                rnum += R0Stats[i]*i            
            if rdenom > 0:
                R0Val = rnum/rdenom
            else:
                R0Val = 0
            print("End:",tend," (",(x.strftime('%Y-%m-%d')),") num:", totS+totN+totInf+totC+totR+totD," numS:",totS," numN:",totN," NumInf:",totInf," NumC:",totC," numR:",totR," numD:",totD," numH:",totH,"(" ,totICU,") R0:",round(R0Val,2))
            
        # write out results to disk in case process dies
        if multiprocess:
            if os.path.exists(ParameterSet.ResultsFolder+"/Results_"+resultsName+".pickle"):
                results = Utils.FileRead(ParameterSet.ResultsFolder+"/Results_"+resultsName+".pickle")
            results[tend] = numInfList
            Utils.FileWrite(ParameterSet.ResultsFolder+"/Results_"+resultsName+".pickle",results)
        else:
            resultsNonMP[tend] = numInfList
        
        gc.collect()
    return resultsNonMP        
