from dataclasses import dataclass
from typing import List
from typing import Union


class Config:
    MAX_U32: int = (2**32) - 1
    ENERGY_TYPE_NUM: int = 5
    ENGINE_TYPE_NUM: int = 3


class WorkShop:
    def __init__(self):
        self.minTi = Config.MAX_U32
        self.maxTi = 0
        self.anyRidOfEngine = [Config.MAX_U32] * Config.ENGINE_TYPE_NUM
        '''第i个元素储存支持第i种设备的area id(rid)，可以是列表（即多个满足条件的area）'''
        return

    def __str__(self):
        return "minTi:{0}\tmaxTi{1}\tanyRidOfEngine{2}\n".format(self.minTi, self.maxTi, self.anyRidOfEngine)


def _parse_file(path: str) -> List[Union[int, List[int]]]:
    """Parse a file as a double sequence of int"""
    with open(path) as fh:
        stream_raw = fh.read().splitlines()
        stream = []
        for line in stream_raw:
            row = [int(el) for el in line.split(" ")]
            if len(row) == 0:
                continue
            if len(row) == 1:
                yield row[0]
            else:
                yield row


@dataclass
class Energy:
    '''
    Define Energy

    Attributes:
        processTime
    '''
    processTime: int


@dataclass
class Region:
    '''
    Define region

    Attributes:
        workshopIndex
        energyType
    '''
    workshopIndex: int
    energyType: int

    @classmethod
    def read(cls, data: List[int]) -> "Region":
        return cls(workshopIndex=data[0], energyType=data[1])


@dataclass
class Window:
    '''
    Define window

    Attributes:
        canSelfLoop
        workshopIndex   
        costFactor
        enginesSupport
    '''
    canSelfLoop: int
    workshopIndex: int
    costFactor: int
    enginesSupport: List[int]

    @classmethod
    def read(cls, data: List[int]) -> "Window":
        canSelfLoop = data[0]
        workshopIndex = data[1]
        costFactor = data[2]
        enginesSupport = data[3: 3 + Config.ENGINE_TYPE_NUM]
        return cls(
            canSelfLoop=canSelfLoop,
            workshopIndex=workshopIndex,
            costFactor=costFactor,
            enginesSupport=enginesSupport,
        )


@dataclass
class Device:
    '''
    Define device

    Attributes: 
        engineType
        energyCosts
    '''
    engineType: int
    energyCosts: List[int]

    @classmethod
    def read(cls, data: List[int]) -> "Device":
        return cls(engineType=data[0], energyCosts=data[1: 1 + Config.ENERGY_TYPE_NUM])


@dataclass
class Edge:
    '''
    Define edge in flow chart

    Attributes:
        type
        sendDevice
        recvDevice
    '''
    type: int
    sendDevice: int
    recvDevice: int

    @classmethod
    def read(cls, data: List[int]) -> "Edge":
        return cls(type=data[0], sendDevice=data[1], recvDevice=data[2])


@dataclass
class Pipeline:
    '''
    Pipeline of the core production line

    Attributes:
        edgeNum
        edgeIndexs
    '''
    edgeNum: int
    edgeIndexs: List[int]

    @classmethod
    def read(cls, edgeNum: int, data: List[int]) -> "Pipeline":

        return cls(edgeNum=edgeNum, edgeIndexs=data[:edgeNum])


@dataclass
class InputData:
    K: int
    "Estimated number of production times of the core production line"
    energys: List[Energy]
    N: int
    "Number of workshops"
    R: int
    "Number of workshop areas"
    regions: List[Region]
    '''List of Regions'''
    L: int
    "Maximum number of loopbacks"
    M: int
    "Number of windows in the first loopback mode"
    W: int
    "Number of windows"
    windows: List[Window]
    D: int
    "Number of devices"
    devices: List[Device]
    E: int
    "Number of edges in a flowchart"
    edges: List[Edge]
    pipeline: Pipeline

    @classmethod
    def from_file(cls, path: str):

        stream = _parse_file(path)

        K = next(stream)

        x = next(stream)
        energys = []
        for i in range(Config.ENERGY_TYPE_NUM):
            energys.append(Energy(x[i]))

        N = next(stream)
        R = next(stream)
        regions = []
        for i in range(R):
            region = Region.read(next(stream))
            regions.append(region)

        L = next(stream)
        M = next(stream)

        W = next(stream)
        windows = []
        for i in range(W):
            window = Window.read(next(stream))
            windows.append(window)

        D = next(stream)
        devices = []
        for i in range(D):
            device = Device.read(next(stream))
            devices.append(device)

        E = next(stream)
        edges = []
        for i in range(E):
            edge = Edge.read(next(stream))
            edges.append(edge)

        pipeline = Pipeline.read(next(stream), next(stream))
        return cls(
            K=K,
            energys=energys,
            N=N,
            R=R,
            regions=regions,
            L=L,
            M=M,
            W=W,
            windows=windows,
            D=D,
            devices=devices,
            E=E,
            edges=edges,
            pipeline=pipeline,
        )


@dataclass
class OutputData:
    deviceNum: int
    regionIndexs: List[int]
    stepNum: int
    timeWindowIndexs: List[int]

    def print(self):
        def PrintVec(vec):
            print(" ".join(str(el) for el in vec))

        print(self.deviceNum)
        PrintVec(self.regionIndexs)

        print(self.stepNum)
        PrintVec(self.timeWindowIndexs)
