import sys
import numpy as np
# from copy import deepcopy
# from itertools import islice, product
from data import InputData, OutputData, Config, Edge
from typing import List

DEBUG = False
alpha = 0.7
beta = 0.7


class WorkShop:
    def __init__(self, index):
        self.index = index
        self.minTi = Config.MAX_U32
        self.maxTi = 0
        self.anyRidOfEngine = [[] for i in range(Config.ENGINE_TYPE_NUM)]
        '''第i个元素储存支持第i种设备的area id(rid)，可以是列表（即多个满足条件的area）'''
        self.energyTypes = []
        return

    def __str__(self) -> str:
        return self.energyTypes.__str__()


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


def computeWindowEntryTimes(inputData: InputData, timeWindowIndexs: List[int]):
    edgeOnCoreProductionLine: List[Edge] = []

    for eid in inputData.pipeline.edgeIndexs:
        edge = inputData.edges[eid]
        edgeOnCoreProductionLine.append(edge)

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


def getMixCost(device, window, workshop):
    rids = workshop.anyRidOfEngine[device.engineType]
    InstallCosts = [
        device.energyCosts[inputData.regions[rid].energyType] for rid in rids]
    # processTime of a single device in an area/region
    ProcessTime = [
        inputData.energys[inputData.regions[rid].energyType].processTime for rid in rids]
    # processTime of a workshop
    processTimes = [
        inputData.energys[energy_id].processTime for energy_id in workshop.energyTypes]
    maxProcessTime = max(processTimes)
    MixCosts = ((1-alpha) * np.array(ProcessTime) + (alpha * maxProcessTime)) * inputData.K + ((1 - beta) * np.array(ProcessTime) + beta * maxProcessTime) * \
        window.costFactor + \
        np.array(InstallCosts)
    MixCost = np.min(MixCosts)
    return MixCost


def getMinInstallCost(device, workshop):
    return np.ma.masked_equal(np.array([device.energyCosts[energyType] for energyType in workshop.energyTypes]), 0, copy=False).min()


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
    # if DEBUG:
    #     print('areaMatchingCost:\t{}'.format(areaMatchingCost))
    #     print('windowPresetCost:\t{}'.format(windowPresetCost))
    #     print('windowProcessCost:\t{}'.format(windowProcessCost))
    #     print('windowProcessTime:\t{}'.format(windowProcessTime))
    #     print('windowEntryTimes:\t{}'.format(windowEntryTimes))
    #     print('windowMatchingCost:\t{}'.format(windowMatchingCost))
    return totalCost


def main(inputData: InputData) -> OutputData:
    """This function must exist with the specified input and output
    arguments for the submission to work"""

    # workshops initialization
    Workshops: List[WorkShop] = []
    for id in range(inputData.N):
        Workshops.append(WorkShop(id))

    # Count the earliest and latest time that one workshop can enter
    for wid in range(inputData.M):
        window = inputData.windows[wid]
        workshop = Workshops[window.workshopIndex]
        minTi = wid
        maxTi = inputData.L * inputData.M + wid
        if minTi < workshop.minTi:
            workshop.minTi = minTi
        if maxTi > workshop.maxTi:
            workshop.maxTi = maxTi

    # the longest possible window passage
    # region
    widOfTi = []
    for loopIndex in range(inputData.L + 1):
        for wid in range(inputData.M):
            widOfTi.append(wid)

    for wid in range(inputData.M, inputData.W):
        window = inputData.windows[wid]
        workshop = Workshops[window.workshopIndex]
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
    # endregion

    # store the devices on the core production line
    isDeviceInPipeline = [False] * inputData.D
    for eid in inputData.pipeline.edgeIndexs:
        edge = inputData.edges[eid]
        isDeviceInPipeline[edge.sendDevice] = True
        isDeviceInPipeline[edge.recvDevice] = True

    # Collect statistics on the workshop region that support a certain
    # type of equipment in the workshop.
    # region
    for rid in range(inputData.R):
        region = inputData.regions[rid]
        nid = region.workshopIndex
        # workshop index in workshops(list) will change due to sort
        workshop = Workshops[nid]
        workshop.energyTypes.append(region.energyType)
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

    # for workshop in workshops:
    #     print(workshop)
    # endregion

    # parse flowchart from edge-representation to node-representation
    # region
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
    # endregion

    # sort workshops
    # region
    # for workshop in workshops:
    #     print(workshop.index, workshop.minTi, workshop.maxTi)

    workshopIndices_sorted_by_minTi = np.argsort(
        [workshop.minTi for workshop in Workshops])
    workshopIndices_sorted_by_maxTi = np.argsort(
        [workshop.maxTi for workshop in Workshops])

    if DEBUG:
        print('workshops')
        for workshop in Workshops:
            print(workshop.index, end=' ')
        print('')
    if DEBUG:
        print('workshops_sorted_by_minTi')
        for id in workshopIndices_sorted_by_minTi:
            print(Workshops[id].index, end=' ')
        print('')
    if DEBUG:
        print('workshops_sorted_by_maxTi')
        for id in workshopIndices_sorted_by_maxTi:
            print(Workshops[id].index, end=' ')
        print('')
    # endregion

    # topological sort
    # region
    queue = Queue()
    # count in edge number for each node
    inCnt = [0] * inputData.D
    # push starting nodes in queue (those don't have incoming edge)
    for did in range(inputData.D):
        inCnt[did] = len(prevEdgeMgr[did])
        if inCnt[did] == 0:
            queue.Push(did)
    while not queue.IsEmpty():
        # current device
        curDid = queue.Pop()
        for eid in nextEdgeMgr[curDid]:
            edge = inputData.edges[eid]
            curDid = edge.recvDevice
            inCnt[curDid] = inCnt[curDid] - 1
            if inCnt[curDid] == 0:
                queue.Push(curDid)

    # print(queue.vec)
    # endregion

    # distribute which area for each device
    ridsOfDid = [[] for i in range(inputData.D)]
    # window scheme for core production line
    widOfPid = [Config.MAX_U32] * (inputData.pipeline.edgeNum + 1)
    for did, device in enumerate(inputData.devices):
        device.minTi = 0
        device.maxTi = len(widOfTi) - 1
        if isDeviceInPipeline[did]:
            device.winTi = None

    # time-first forward greedy
    # find the earliest possible ti of a device
    # region
    # pid is the order of the device on the core production line
    pid = 0
    for curDid in queue.vec:
        device = inputData.devices[curDid]
        if isDeviceInPipeline[curDid]:
            for ti in range(device.minTi, device.maxTi):
                wid = widOfTi[ti]
                window = inputData.windows[wid]
                # if the window doesn't support pre-processing of the device of this engine type, i.e window selection constraint
                if not window.enginesSupport[device.engineType]:
                    continue
                workshop = Workshops[window.workshopIndex]
                # print(window.workshopIndex, workshop.index)
                # if the area doesn't support energy of the device of this engine type, i.e device installation constraint
                if len(workshop.anyRidOfEngine[device.engineType]) == 0:
                    continue
                # select this window for the window scheme of the core production line
                # widOfPid[pid] = wid
                pid = pid + 1
                device.winTi = ti

                # put current device to those region/areas
                # ridsOfDid[curDid] = workshop.anyRidOfEngine[device.engineType]
                break
        else:
            for i in workshopIndices_sorted_by_minTi:
                workshop = Workshops[i]
                if len(workshop.anyRidOfEngine[device.engineType]) == 0:
                    continue
                if workshop.maxTi >= device.minTi:
                    #     ridsOfDid[curDid] = workshop.anyRidOfEngine[device.engineType]
                    break
        # if len(ridsOfDid[curDid]) == 0:
        #     print("wrong in %d" % curDid)
        #     exit()

        # update minTi for the next device
        for eid in nextEdgeMgr[curDid]:
            edge = inputData.edges[eid]
            postDid = edge.recvDevice
            postDevice = inputData.devices[postDid]
            postDevice.minTi = max(
                postDevice.minTi, workshop.minTi + (edge.type == 0))
            if isDeviceInPipeline[curDid] and isDeviceInPipeline[postDid]:
                postDevice.minTi = max(
                    postDevice.minTi, device.winTi + (edge.type == 0))

    # endregion

    # time-first backward greedy
    # find the latest possible ti of a device
    # region
    pid = inputData.pipeline.edgeNum  # start from right most
    for curDid in reversed(queue.vec):
        device = inputData.devices[curDid]
        if isDeviceInPipeline[curDid]:
            for ti in range(device.maxTi, device.winTi - 1, -1):
                wid = widOfTi[ti]
                window = inputData.windows[wid]
                # if the window doesn't support pre-processing of the device of this engine type, i.e window selection constraint
                if not window.enginesSupport[device.engineType]:
                    continue
                workshop = Workshops[window.workshopIndex]
                # if the area doesn't support energy of the device of this engine type, i.e device installation constraint
                if len(workshop.anyRidOfEngine[device.engineType]) == 0:
                    continue
                # select this window for the window scheme of the core production line
                # widOfPid[pid] = wid
                pid = pid - 1
                device.winTi = ti

                # put current device to those region/areas
                # ridsOfDid[curDid] = workshop.anyRidOfEngine[device.engineType]
                break
        else:
            for i in reversed(workshopIndices_sorted_by_maxTi):
                workshop = Workshops[i]
                if len(workshop.anyRidOfEngine[device.engineType]) == 0:
                    continue
                if workshop.minTi <= device.maxTi:
                    #     ridsOfDid[curDid] = workshop.anyRidOfEngine[device.engineType]
                    break
        # if len(ridsOfDid[curDid]) == 0:
        #     print("wrong in %d" % curDid)
        #     exit()

        # update maxTi for the next device
        for eid in prevEdgeMgr[curDid]:
            edge = inputData.edges[eid]
            preDid = edge.sendDevice
            preDevice = inputData.devices[preDid]
            # maxTiOfDid stores the latest possible timestamp given by the topologival order
            # the requestTi is computed from workshop.maxTi, as if every time the device enter the workshop is the first time (no need to count the maximum loopback)
            preDevice.maxTi = min(
                preDevice.maxTi, workshop.maxTi - (edge.type == 0))
            if isDeviceInPipeline[curDid] and isDeviceInPipeline[preDid]:
                preDevice.maxTi = min(
                    preDevice.maxTi, device.winTi - (edge.type == 0))

    # endregion
    # you only loop once this time (YOLO)
    pid = 0
    for curDid in queue.vec:
        device = inputData.devices[curDid]
        if isDeviceInPipeline[curDid]:
            # all possible wids
            wids = [widOfTi[ti] for ti in range(device.minTi, device.maxTi+1)
                    if inputData.windows[widOfTi[ti]].enginesSupport[device.engineType] and
                    len(Workshops[inputData.windows[widOfTi[ti]].workshopIndex].anyRidOfEngine[device.engineType]) > 0]
            windows = [inputData.windows[wid] for wid in wids]
            workshops = [Workshops[window.workshopIndex] for window in windows]
            # cost greedy
            mixCosts = [getMixCost(device, window, workshop)
                        for (window, workshop) in zip(windows, workshops)]
            idMin = np.argmin(mixCosts)
            wid = wids[idMin]
            workshop = workshops[idMin]
            # select this window for the window scheme of the core production line
            widOfPid[pid] = wid
            pid = pid + 1
            device.winTi = widOfTi.index(wid)
            # put current device to those region/areas
            ridsOfDid[curDid] = workshop.anyRidOfEngine[device.engineType]
        else:
            workshops = [Workshops[i] for i in workshopIndices_sorted_by_minTi if (
                Workshops[i].minTi <= device.maxTi or Workshops[i].maxTi >= device.minTi) and len(Workshops[i].anyRidOfEngine[device.engineType]) > 0]
            minInstallCosts = [getMinInstallCost(
                device, workshop) for workshop in workshops]
            idMin = np.argmin(minInstallCosts)
            workshop = workshops[idMin]
            ridsOfDid[curDid] = workshop.anyRidOfEngine[device.engineType]
        if len(ridsOfDid[curDid]) == 0:
            print("wrong in %d" % curDid)
            exit()

        # update minTi for the next device
        for eid in nextEdgeMgr[curDid]:
            edge = inputData.edges[eid]
            postDid = edge.recvDevice
            postDevice = inputData.devices[postDid]
            postDevice.minTi = max(
                postDevice.minTi, workshop.minTi + (edge.type == 0))
            if isDeviceInPipeline[curDid] and isDeviceInPipeline[postDid]:
                postDevice.minTi = max(
                    postDevice.minTi, device.winTi + (edge.type == 0))

    for did in range(inputData.D):
        print(inputData.devices[did].minTi, end='')
    print('')
    for did in range(inputData.D):
        print(inputData.devices[did].maxTi, end='')
    print('')

    ridOfDid = []
    windowEntryTimes, deviceOnCoreProductionLine = computeWindowEntryTimes(
        inputData, widOfPid)
    for did, rids in enumerate(ridsOfDid):
        InstallCosts = [
            inputData.devices[did].energyCosts[inputData.regions[rid].energyType] for rid in rids]
        if not isDeviceInPipeline[did]:
            idOfMinInstallCost = min(
                range(len(InstallCosts)), key=InstallCosts.__getitem__)
            ridOfDid.append(rids[idOfMinInstallCost])
        else:
            # processTime of a single device in an area/region
            ProcessTime = [
                inputData.energys[inputData.regions[rid].energyType].processTime for rid in rids]
            # processTime of a workshop
            workshop = Workshops[inputData.regions[rids[0]].workshopIndex]
            # print(workshop.index)
            processTimes = [
                inputData.energys[energy_id].processTime for energy_id in workshop.energyTypes]
            maxProcessTime = max(processTimes)
            # print(ProcessTime)
            # print(processTimes)
            # print(maxProcessTime)
            wid = widOfPid[deviceOnCoreProductionLine.index(did)]
            WindowEntryTimes = windowEntryTimes[wid]
            MixCost = ((1-alpha) * np.array(ProcessTime) + (alpha * maxProcessTime)) * inputData.K * WindowEntryTimes + ((1 - beta) * np.array(ProcessTime) + beta * maxProcessTime) * \
                inputData.windows[wid].costFactor + np.array(InstallCosts)
            idMinMixCost = np.argmin(MixCost)
            ridOfDid.append(rids[idMinMixCost])

    # print(ridOfDid)
    outputData_FV = OutputData(
        deviceNum=inputData.D,
        regionIndexs=ridOfDid,
        stepNum=inputData.pipeline.edgeNum + 1,
        timeWindowIndexs=widOfPid,
    )

    return outputData_FV


if __name__ == "__main__":
    # The following is only used for local tests
    # inputData = InputData.from_file(sys.argv[1])
    inputData = InputData.from_file('./sample/sample.in')
    # inputData = InputData.from_file('./sample/sample_test.in')
    # inputData = InputData.from_file('./sample/sample scratch.in')
    outputData = main(inputData)
    outputData.print()
    print(computeCost(inputData, outputData))
