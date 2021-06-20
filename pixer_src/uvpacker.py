from math import inf
from bmesh.types import BMFace
from typing import Dict, List
from mathutils import Vector
from pixer_src.xface import XFace


def simple_uv_packing(uv_island_map: Dict[BMFace, List[XFace]], pixel_2d_size: float):
    uv_islands = _uv_islands_map_to_list(uv_island_map)
    left = 0
    next_left = 0
    bot = 0
    for uv_island in uv_islands:
        uv_island_left = _get_uv_island_left(uv_island)
        uv_island_bot = _get_uv_island_bot(uv_island)
        displacement = Vector((left - uv_island_left, bot - uv_island_bot))
        for xface in uv_island:
            for i in range(xface.get_face_length()):
                xface.update_uv(i, xface.get_uv(i) + displacement)
        next_left = max(next_left, _get_uv_island_width(uv_island))
        bot += _get_uv_island_height(uv_island) + pixel_2d_size
        if bot > 1:
            bot = 0
            left = left + next_left + pixel_2d_size
            next_left = 0


def _uv_islands_map_to_list(uv_islands_map):
    uv_island_list = []
    already_parsed = set()
    for uv_island in uv_islands_map.values():
        face_ids = []
        for xface in uv_island:
            face_ids.append(xface.get_face().index)
        face_ids.sort()
        face_ids_hash = ' '.join([str(elem) for elem in face_ids])
        if face_ids_hash not in already_parsed and uv_island:
            already_parsed.add(face_ids_hash)
            uv_island_list.append(uv_island)
    return uv_island_list


def _get_uv_island_left(uv_island: [XFace]) -> float:
    left = inf
    for xface in uv_island:
        for uv in xface.get_all_uvs():
            if uv.x < left:
                left = uv.x
    return left


def _get_uv_island_bot(uv_island: [XFace]) -> float:
    bot = inf
    for xface in uv_island:
        for uv in xface.get_all_uvs():
            if uv.y < bot:
                bot = uv.y
    return bot


def _get_uv_island_right(uv_island: [XFace]) -> float:
    right = -inf
    for xface in uv_island:
        for uv in xface.get_all_uvs():
            if uv.x > right:
                right = uv.x
    return right


def _get_uv_island_top(uv_island: [XFace]) -> float:
    top = -inf
    for xface in uv_island:
        for uv in xface.get_all_uvs():
            if uv.y > top:
                top = uv.y
    return top


def _get_uv_island_width(uv_island: [XFace]) -> float:
    return abs(_get_uv_island_left(uv_island) - _get_uv_island_right(uv_island))


def _get_uv_island_height(uv_island: [XFace]) -> float:
    return abs(_get_uv_island_bot(uv_island) - _get_uv_island_top(uv_island))
