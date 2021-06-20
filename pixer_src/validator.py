from bmesh.types import BMesh
from pixer_src.logger import log, ERROR


def validate(bm: BMesh):
    vertices = set()
    for vert in bm.verts:
        if vert.co.copy().freeze() in vertices:
            log(ERROR, "The vert " + str(vert.co.copy().freeze()) + " is already in the set, "
                                                                    "it is probably a duplicate!")
        vertices.add(vert.co.copy().freeze())

    if len(bm.verts) != len(vertices):
        raise Exception("There are duplicated vertices! Cannot proceed!")
