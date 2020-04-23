# -----------------------------------------------------------------------------
# Region.py creates the location specific attributes
# -----------------------------------------------------------------------------
import random
import time
import math

import LocalPopulation

import ParameterSet


class Region:
    def __init__(self, RegionalLocations, RegionalInteractionMatrixList,
                 RegionId, RegionListGuide,HospitalTransitionMatrixList,PopulationParameters,DiseaseParameters,SimEndDate):
        """
        class represents a local location for the agent

        :param localgriddata: spatial 2D array with population density of local
        :type localgriddata: array
        :param agedist: age distribution [number of child, number of adults]
        :type agedist: list
        """
        # self.RegionalLocations = RegionalLocations
        # self.RegionalInteractionMatrixList = RegionalInteractionMatrixList
        self.RegionId = RegionId
        self.Locations = {}
        self.IsWhuhanMktRegion = 0
        
        # create local population for each point in the local block
        for i in range(0, len(RegionalLocations)):
            GLP = RegionalLocations[i]
            HTM = []
            if len(HospitalTransitionMatrixList) > 0:
                HTM = HospitalTransitionMatrixList[i]
                    
            if(GLP.getGlobalId()==ParameterSet.WuhanMktLocalPopId):
                self.IsWhuhanMktRegion = 1
                
            LP = LocalPopulation. \
                LocalPopulation(GLP.getGlobalId(), GLP.getPopulationAmt(),
                                GLP.getHHSizeDist(), GLP.getHHSizeAgeDist(),
                                RegionalInteractionMatrixList[i], self.RegionId,
                                RegionListGuide,HTM,GLP.getPopulationDensity(),GLP.getLocalIdentification(),GLP.getRegionalIdentification(),PopulationParameters,DiseaseParameters,SimEndDate)
            self.Locations[GLP.getGlobalId()] = LP
            
            if ParameterSet.debugmodelevel >= ParameterSet.debugnotice:
                print("created population ", GLP.getLocalIdentification(), " (", GLP.getGlobalId(), ") in region ",RegionId," with ",
                      GLP.getPopulationAmt(), " people")
            # print(RegionalInteractionMatrixList[i])

    def IsThisWhuhanMktRegion(self):
        return self.IsWhuhanMktRegion
    
    def runTimePeriod(self, tend):
        offPopQueueEvents = []
        regionStats = {}
        R0Stats = {}
        hospitalStats = {}
        numEvents = 0
        for LPKey in self.Locations.keys():
            LP = self.Locations[LPKey]
            op, NE = LP.runTime(tend)
            numEvents += NE
            offPopQueueEvents.extend(op)
            regionStats[LPKey] = LP.reportPopulationStats()
            
        return regionStats, offPopQueueEvents, numEvents

    def getInfectedNums(self):
        infectedNums = {}
        for LPKey in self.Locations.keys():
            LP = self.Locations[LPKey]
            infectedNums.update(LP.reportNumInfected())

        return infectedNums

    def getInfectionEvents(self):
        infEvents = []
        for LPKey in self.Locations.keys():
            LP = self.Locations[LPKey]
            agentEvents = LP.getInfectionEvents()
            infEvents.extend(agentEvents)
        print(infEvents)
        
    def infectRandomAgents(self,tend,numInfect,OneLocalOnly=True,LPID =-1):
        # Create off popqueue
        offPopQueueEvents = []
        # If we are only infecting on region
        if OneLocalOnly:
            if LPID < 0:
                if ParameterSet.WuhanMktLocalPopId >= 0:
                    LPID = ParameterSet.WuhanMktLocalPopId
                else:
                    LPID = random.choice(list(self.Locations.keys()))
                
            LP = self.Locations[LPID]
            for i in range(0,numInfect):
                op = LP.infectRandomAgent(tend)
                offPopQueueEvents.extend(op)
            
        else:
            LPIDs = []
            for i in range(0,numInfect):
                LPIDs.append(random.choice(list(self.Locations.keys())))
            
            LPIDs.sort()
            LPID = -1
            for i in range(0,len(LPIDs)):
                LPID = LPIDs[i]
                LP = self.Locations[LPID]
                op = LP.infectRandomAgent(tend)
                offPopQueueEvents.extend(op)
                    
        return offPopQueueEvents


    def addEventsFromOtherLocalPopulations(self,RegionReconciliationEvents):
        for QE in RegionReconciliationEvents:
            LPID = QE.getLocalPopulationId()
            LP = self.Locations[LPID]
            LP.addEventsFromOtherLocalPopulations(QE)
            
        return self.getRegionStats()
                    
    def getRegionStats(self):
        regionStats = {}
        for LPKey in self.Locations.keys():
            LP = self.Locations[LPKey]
            regionStats[LPKey] = LP.reportPopulationStats()
        return regionStats

    def getHospitalOccupancy(self):
        hospLists = {}
        for LPKey in self.Locations.keys():
            LP = self.Locations[LPKey]
            hospLists[LPKey] = LP.getHospitalOccupancy()
        return hospLists
        
    def getR0Stats(self):
        R0Lists = {}
        for LPKey in self.Locations.keys():
            LP = self.Locations[LPKey]
            R0Lists[LPKey] = LP.getR0Stats()
        return R0Lists  
        
    def getAgeStats(self):
        AgeLists = {}
        for LPKey in self.Locations.keys():
            LP = self.Locations[LPKey]
            AgeLists[LPKey] = LP.getAgeStats()
        return AgeLists        