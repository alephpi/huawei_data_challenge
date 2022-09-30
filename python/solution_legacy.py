import sys
import numpy as np
from itertools import islice, product
from data import InputData, OutputData, Config, Edge
from typing import List

DEBUG = False


def countWindowEntryTimes(inputData: InputData, timeWindowIndexs: List[int]):
    edgeOnCoreProductionLine: List[Edge] = []

    for eid in inputData.pipeline.edgeIndexs:
        edge = inputData.edges[eid]
        edgeOnCoreProductionLine.append(edge)
        # print("edge {} type {}".format(eid, edge.type))

    deviceOnCoreProductionLine: List[int] = []
    for edge in edgeOnCoreProductionLine:
        deviceOnCoreProductionLine.append(edge.sendDevice)
    deviceOnCoreProductionLine.append(edge.recvDevice)

    windowEntryTimes: List[int] = [0] * inputData.W
    for id, edge in enumerate(edgeOnCoreProductionLine):
        wid = timeWindowIndexs[id]
        wid_next = timeWindowIndexs[id + 1]
        windowEntryTimes[wid] += 1
        # if two consecutive windows are the same and the edge is red, i.e collabarative relation
        # only count once entry time
        if wid == wid_next and edge.type == 1:
            windowEntryTimes[wid] -= 1  # minus one since count one more time
            # print("collaboration in window {}".format(wid))
    # Don't forget the last device
    windowEntryTimes[wid_next] += 1
    return windowEntryTimes, deviceOnCoreProductionLine


def computeCost(inputData: InputData, outputData: OutputData):
    areaMatchingCost: int = 0
    windowMatchingCost: int = 0
    for did in range(outputData.deviceNum):
        device = inputData.devices[did]
        rid = outputData.regionIndexs[did]

        # compute areaMatchingCost
        energyType = inputData.regions[rid].energyType
        installCost = device.energyCosts[energyType]
        areaMatchingCost += installCost

    # get the devices on core production line
    edgeOnCoreProductionLine: List[Edge] = []
    deviceOnCoreProductionLine: List[int] = []
    for eid in inputData.pipeline.edgeIndexs:
        edge = inputData.edges[eid]
        edgeOnCoreProductionLine.append(edge)
        # print("edge {} type {}".format(eid, edge.type))
    for edge in edgeOnCoreProductionLine:
        deviceOnCoreProductionLine.append(edge.sendDevice)
    deviceOnCoreProductionLine.append(edge.recvDevice)

    # find out window process time (device -> area -> energy -> processTime)
    # do not using * since list is not elementary type, * will make shallow copy
    windowProcessTimeRaw: List[List[int]] = [[0] for i in range(inputData.W)]
    for id, did in enumerate(deviceOnCoreProductionLine):
        wid = outputData.timeWindowIndexs[id]
        rid = outputData.regionIndexs[did]
        energyType = inputData.regions[rid].energyType
        processTime = inputData.energys[energyType].processTime
        windowProcessTimeRaw[wid].append(processTime)
    windowProcessTime = list(map(max, windowProcessTimeRaw))
    # compute entry time
    windowEntryTimes: List[int] = [0] * inputData.W
    for id, edge in enumerate(edgeOnCoreProductionLine):
        wid = outputData.timeWindowIndexs[id]
        wid_next = outputData.timeWindowIndexs[id + 1]
        windowEntryTimes[wid] += 1
        # if two consecutive windows are the same and the edge is red, i.e collabarative relation
        # only count once entry time
        if wid == wid_next and edge.type == 1:
            windowEntryTimes[wid] -= 1  # minus one since count one more time
            # print("collaboration in window {}".format(wid))
    # Don't forget the last device
    windowEntryTimes[wid_next] += 1

    windowProcessCost = 0
    windowPresetCost = 0
    for wid in range(inputData.W):
        entryTimes = windowEntryTimes[wid]
        processTime = windowProcessTime[wid]
        windowProcessCost += processTime * entryTimes
        windowPresetCost += processTime * inputData.windows[wid].costFactor
    windowProcessCost *= inputData.K
    windowMatchingCost = windowProcessCost + windowPresetCost
    totalCost = areaMatchingCost + windowMatchingCost
    if DEBUG:
        print('areaMatchingCost:\t{}'.format(areaMatchingCost))
        print('windowPresetCost:\t{}'.format(windowPresetCost))
        print('windowProcessCost:\t{}'.format(windowProcessCost))
        print('windowProcessTime:\t{}'.format(windowProcessTime))
        print('windowEntryTimes:\t{}'.format(windowEntryTimes))
        print('windowMatchingCost:\t{}'.format(windowMatchingCost))
    return totalCost


class WorkShop:
    def __init__(self, index):
        self.index = index
        self.minTi = Config.MAX_U32
        self.maxTi = 0
        self.anyRidOfEngine = [[] for i in range(Config.ENGINE_TYPE_NUM)]
        '''第i个元素储存支持第i种设备的area id(rid)，可以是列表（即多个满足条件的area）'''
        return


# Topological sort
class Queue:
    def __init__(self):
        self.vec = []
        self.headIndex = 0
        self.tailIndex = 0
        return

    def Push(self, item):
        self.vec.append(item)
        self.tailIndex = self.tailIndex + 1
        return

    def IsEmpty(self):
        return self.headIndex == self.tailIndex

    def Pop(self):
        if self.headIndex >= self.tailIndex:
            print("[Err] Queue Pop")
            return "Err"
        item = self.vec[self.headIndex]
        self.headIndex = self.headIndex + 1
        return item


def main(inputData: InputData) -> OutputData:
    """This function must exist with the specified input and output
    arguments for the submission to work"""

    workshops: List[WorkShop] = []
    for id in range(inputData.N):
        workshops.append(WorkShop(id))

    # Count the earliest and latest time that one workshop can enter
    for wid in range(inputData.M):
        window = inputData.windows[wid]
        workshop = workshops[window.workshopIndex]
        minTi = wid
        maxTi = inputData.L * inputData.M + wid
        if minTi < workshop.minTi:
            workshop.minTi = minTi
        if maxTi > workshop.maxTi:
            workshop.maxTi = maxTi

    # the longest possible window passage
    widOfTi = []
    for loopIndex in range(inputData.L + 1):
        for wid in range(inputData.M):
            widOfTi.append(wid)

    for wid in range(inputData.M, inputData.W):
        window = inputData.windows[wid]
        workshop = workshops[window.workshopIndex]
        widOfTi.append(wid)
        # improvable minTi and maxTi
        minTi = len(widOfTi) - 1
        if minTi < workshop.minTi:
            workshop.minTi = minTi
        if window.canSelfLoop:
            for loopIndex in range(inputData.L):
                widOfTi.append(wid)
        maxTi = len(widOfTi) - 1
        if maxTi > workshop.maxTi:
            workshop.maxTi = maxTi

    if DEBUG:
        for workshop in workshops:
            print(workshop.index)
    workshops.sort(key=lambda de: de.minTi)
    if DEBUG:
        for workshop in workshops:
            print(workshop.index)

    # store the devices on the core production line
    isDeviceInPipeline = [False] * inputData.D
    for eid in inputData.pipeline.edgeIndexs:
        edge = inputData.edges[eid]
        isDeviceInPipeline[edge.sendDevice] = True
        isDeviceInPipeline[edge.recvDevice] = True

    # Make statistics of the workshop area where
    # Collect statistics on the workshop region that support a certain
    # type of equipment in the workshop.

    for rid in range(inputData.R):
        region = inputData.regions[rid]
        nid = region.workshopIndex
        # workshop index in workshops(list) will change due to sort
        workshop = workshops[nid]
        if region.energyType == 0:
            # this can be changed by a list of rid
            workshop.anyRidOfEngine[0].append(rid)
            workshop.anyRidOfEngine[1].append(rid)
        elif region.energyType == 1:
            workshop.anyRidOfEngine[0].append(rid)
        elif region.energyType == 2:
            workshop.anyRidOfEngine[1].append(rid)
        elif region.energyType == 3:
            workshop.anyRidOfEngine[2].append(rid)
        elif region.energyType == 4:
            workshop.anyRidOfEngine[2].append(rid)

    # delete the duplicate area in anyRidOfEngine.
    # for workshop in workshops:
    #     for i in range(len(workshop.anyRidOfEngine)):
    #         workshop.anyRidOfEngine[i] = list(set(workshop.anyRidOfEngine[i]))

    # parse flowchart from edge-representation to node-representation
    # e.g nextEdgeMgr[0] stores the 0-th node's outgoing edge
    nextEdgeMgr = []
    prevEdgeMgr = []
    for did in range(inputData.D):
        nextEdgeMgr.append([])
        prevEdgeMgr.append([])

    for eid in range(inputData.E):
        edge = inputData.edges[eid]
        nextEdgeMgr[edge.sendDevice].append(eid)
        prevEdgeMgr[edge.recvDevice].append(eid)

    queue = Queue()
    # count in edge number for each node
    inCnt = [0] * inputData.D
    # push starting nodes in queue (those don't have incoming edge)
    for did in range(inputData.D):
        inCnt[did] = len(prevEdgeMgr[did])
        if inCnt[did] == 0:
            queue.Push(did)

    # distribute which area for each device
    ridsOfDid = [[] for i in range(inputData.D)]
    minTiOfDid = [0] * inputData.D

    # pid is the order of the device on the core production line
    pid = 0
    preTi = 0
    # window scheme for core production line
    widOfPid = [Config.MAX_U32] * (inputData.pipeline.edgeNum + 1)

    while not queue.IsEmpty():
        # current device
        curDid = queue.Pop()
        # print(curDid)
        if isDeviceInPipeline[curDid]:
            startTi = minTiOfDid[curDid]
            engineType = inputData.devices[curDid].engineType
            # ...
            if pid != 0:
                edge = inputData.edges[inputData.pipeline.edgeIndexs[pid - 1]]
                startTi = max(startTi, preTi + (edge.type == 0))

            for ti in range(startTi, len(widOfTi)):
                wid = widOfTi[ti]
                window = inputData.windows[wid]
                # if the window doesn't support pre-processing of the device of this engine type, i.e window selection constraint
                if not window.enginesSupport[engineType]:
                    continue
                workshop = workshops[window.workshopIndex]

                # if the area doesn't support energy of the device of this engine type, i.e device installation constraint
                if len(workshop.anyRidOfEngine[engineType]) == 0:
                    continue

                # select this window for the window scheme of the core production line
                widOfPid[pid] = wid
                pid = pid + 1
                preTi = ti

                # put current device to those region/areas
                ridsOfDid[curDid] = workshop.anyRidOfEngine[engineType]
                break
        else:
            engineType = inputData.devices[curDid].engineType
            for i in range(inputData.N):
                workshop = workshops[i]
                if len(workshop.anyRidOfEngine[engineType]) == 0:
                    continue

                if workshop.maxTi >= minTiOfDid[curDid]:
                    ridsOfDid[curDid] = workshop.anyRidOfEngine[engineType]
                    break
        if len(ridsOfDid[curDid]) == 0:
            print("wrong in %d" % curDid)
            exit()
        # record the workshop where the current device installed
        workshop = workshops[inputData.regions[ridsOfDid[curDid]
                                               [0]].workshopIndex]
        for eid in nextEdgeMgr[curDid]:
            edge = inputData.edges[eid]
            curDid = edge.recvDevice
            if edge.type == 0:
                requestTi = workshop.minTi + 1
            else:
                requestTi = workshop.minTi
            minTiOfDid[curDid] = max(minTiOfDid[curDid], requestTi)
            inCnt[curDid] = inCnt[curDid] - 1
            if inCnt[curDid] == 0:
                queue.Push(curDid)

    # print(ridsOfDid)

    ridOfDid = []
    windowEntryTimes, deviceOnCoreProductionLine = countWindowEntryTimes(
        inputData, widOfPid)
    for did, rids in enumerate(ridsOfDid):
        InstallCosts = [
            inputData.devices[did].energyCosts[inputData.regions[rid].energyType] for rid in rids]
        if not isDeviceInPipeline[did]:
            idOfMinInstallCost = min(
                range(len(InstallCosts)), key=InstallCosts.__getitem__)
            ridOfDid.append(rids[idOfMinInstallCost])
        else:
            ProcessTime = [
                inputData.energys[inputData.regions[rid].energyType].processTime for rid in rids]
            wid = widOfPid[deviceOnCoreProductionLine.index(did)]
            WindowEntryTimes = windowEntryTimes[wid]
            MixCost = np.array(ProcessTime) * inputData.K * WindowEntryTimes + np.array(
                ProcessTime) * inputData.windows[wid].costFactor + np.array(InstallCosts)
            idMinMixCost = np.argmin(MixCost)
            ridOfDid.append(rids[idMinMixCost])

    print(ridOfDid)
    outputData_FV = OutputData(
        deviceNum=inputData.D,
        regionIndexs=ridOfDid,
        stepNum=inputData.pipeline.edgeNum + 1,
        timeWindowIndexs=widOfPid,
    )

    return outputData_FV

    # print(possible_regionIndexs)
    # n_selected  = min(int(len(possible_regionIndexs)/10), 100)
    # selected_regionIndexs = random.sample(possible_regionIndexs, n_selected)

    # cost = float("inf")
    # outputData = OutputData(
    #     deviceNum=inputData.D,
    #     regionIndexs=[],
    #     stepNum=inputData.pipeline.edgeNum + 1,
    #     timeWindowIndexs=widOfPid,
    # )
    # curOutputData = OutputData(
    #     deviceNum=inputData.D,
    #     regionIndexs=[],
    #     stepNum=inputData.pipeline.edgeNum + 1,
    #     timeWindowIndexs=widOfPid,
    # )
    # # reduce dimension of ridsOfDid
    # for did in range(InputData.D):
    #     if not isDeviceInPipeline[did]:
    #         ridsOfDid[did]

    # for region_device in islice(product(*ridsOfDid), 3000):
    #     curOutputData.regionIndexs = region_device
    #     curCost = computeCost(inputData, curOutputData)
    #     if curCost < cost:
    #         cost = curCost
    #         outputData.regionIndexs = region_device

    # return outputData


if __name__ == "__main__":
    # The following is only used for local tests
    import sys
    # import constants

    # inputData = InputData.from_file(sys.argv[1])
    inputData = InputData.from_file('./sample/sample.in')
    outputData = main(inputData)
    outputData.print()
    print(computeCost(inputData, outputData))
    # print(computeCost(inputData, outputData))
    # outputData = constants.sample_output
    # print('sample_output')
    # outputData.print()
    # print(computeCost(inputData, outputData))

    # for i in range(1,11,1):
    #     outputData = eval('constants.sample_output{}'.format(i))
    #     print('sample_output{}'.format(i))
    #     # outputData.print()
    #     print(computeCost(inputData, outputData))
