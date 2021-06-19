# PIXEL UV SOLVER
# This is the one that does the work. It heavily relies on the XFace class
# to know the order in which it should solve the faces and other things
from typing import Set

from .logger import *
from mathutils import Vector
from .xface import XFace
from .utils import sign
from math import floor

multiplier = 0.5


def solve_face(xface: XFace, pixels_per_3d: int, pixel_2d_size: float):
    # Convert all edges to uv basis
    prom = 0.0
    for i in range(xface.get_face_length()):
        length_3d = xface.get_edge(i).length
        prom += _get_length2d(length_3d, pixels_per_3d, pixel_2d_size) / length_3d
    prom = prom / float(xface.get_face_length())

    # Scale to promedium on scale size
    for i in range(xface.get_face_length()):
        vertex3d = xface.get_basis_converted_vertex(i)
        vertex2d = vertex3d.to_2d()
        xface.update_uv(i, vertex2d * prom)

    # Move one vertex to 0,0 then move everybody the same amount
    displacement = xface.get_uv(0)
    for i in range(xface.get_face_length()):
        xface.update_uv(i, xface.get_uv(i) - displacement)

    # Snap all uvs to pixels
    snap_face_uv_to_pixel(xface, False, pixel_2d_size)

    # Correct wrong edges and snap again
    _fix_wrong_edges(xface, pixels_per_3d, pixel_2d_size)
    snap_face_uv_to_pixel(xface, False, pixel_2d_size)
    xface.solve()


def _get_length2d(length3d: float, pixels_per_3d: int, pixel_2d_size: float):
    length2d: float = (pixels_per_3d * length3d) * pixel_2d_size
    return length2d


def _fix_wrong_edges(xface: XFace, pixels_per_3d: int, pixel_2d_size: float):
    for edge in xface.get_horizontal_edges():
        pixels_3d = _pixels_3d(xface.get_edge(edge).length, pixels_per_3d)
        pixels_2d = _pixels_2d(xface.get_uv_edge(edge).length, pixel_2d_size)
        if pixels_3d != pixels_2d:
            _fix_edge(xface, edge, pixels_per_3d, pixel_2d_size, pixels_3d - pixels_2d, True)

    for edge in xface.get_vertical_edges():
        pixels_3d = _pixels_3d(xface.get_edge(edge).length, pixels_per_3d)
        pixels_2d = _pixels_2d(xface.get_uv_edge(edge).length, pixel_2d_size)
        if pixels_3d != pixels_2d:
            _fix_edge(xface, edge, pixels_per_3d, pixel_2d_size, pixels_3d - pixels_2d, False)


def _pixels_3d(length3d: float, pixels_per_3d) -> int:
    return int(round(length3d * pixels_per_3d))


def _pixels_2d(length2d: float, pixel_2d_size: float):
    return int(round(length2d / pixel_2d_size))


def _fix_edge(xface: XFace, edge: int, pixels_per_3d: int, pixel_2d_size: float, adjust: int, horizontally: bool):
    if horizontally:
        adjust = adjust * sign(xface.get_uv(edge + 1).x - xface.get_uv(edge).x)
    else:
        adjust = adjust * sign(xface.get_uv(edge + 1).y - xface.get_uv(edge).y)
    next_vertex = xface.get_index(edge + 1)

    vertices_allowed_to_move = _get_number_of_vertices_allowed_to_move(xface, pixels_per_3d, pixel_2d_size, edge,
                                                                       edge, next_vertex, adjust, horizontally)
    if vertices_allowed_to_move is not None:
        _adjust_vertices_recursive(xface, pixel_2d_size, next_vertex, vertices_allowed_to_move, False, adjust,
                                   horizontally)
        return

    # Try the other way around just in case
    vertices_allowed_to_move = _get_number_of_vertices_allowed_to_move(xface, pixels_per_3d, pixel_2d_size, next_vertex,
                                                                       next_vertex, edge, adjust, horizontally)
    if vertices_allowed_to_move is not None:
        _adjust_vertices_recursive(xface, pixel_2d_size, edge, vertices_allowed_to_move, True, adjust, horizontally)


def _get_number_of_vertices_allowed_to_move(xface: XFace, pixels_per_3d: int, pixel_2d_size: float, init: int,
                                            from_vertex: int, vertex: int, amount: int, move_hor: bool):
    if vertex == init:
        return None

    length = xface.get_face_length()
    clockwise = from_vertex > vertex or (from_vertex == 0 and vertex == length - 1)

    next_vertex = (vertex + length - 1) % length if clockwise else (vertex + 1) % length
    edge = next_vertex if clockwise else vertex

    if edge not in xface.get_vertical_edges() + xface.get_horizontal_edges():
        return 1

    edge_3d = xface.get_edge(edge)
    edge_2d = xface.get_uv_edge(edge)

    pixels_3d = _pixels_3d(edge_3d.length, pixels_per_3d)
    pixels_2d = _pixels_2d(edge_2d.length, pixel_2d_size)
    if pixels_3d != pixels_2d:
        if _movement_required_is_the_same_as_movement_desired(pixels_3d, pixels_2d, amount,
                                                              edge in xface.get_horizontal_edges(), move_hor):
            return 1

    result = _get_number_of_vertices_allowed_to_move(xface, pixels_per_3d, pixel_2d_size, init, vertex, next_vertex,
                                                     amount, move_hor)
    return None if result is None else 1 + result


def _movement_required_is_the_same_as_movement_desired(pixels_3d: int, pixels_2d: int, amount: int,
                                                       edge_is_horizontal: bool, move_hor: bool) -> bool:
    desired_amount = pixels_3d - pixels_2d
    return desired_amount == amount and edge_is_horizontal == move_hor


def _adjust_vertices_recursive(xface: XFace, pixel_2d_size: float, vertex: int, vertex_remaining: int, clockwise: bool,
                               amount: int, horizontally: bool):
    if vertex_remaining == 0:
        return

    if horizontally:
        xface.update_uv(vertex, xface.get_uv(vertex) + Vector((pixel_2d_size * amount, 0.0)))
    else:
        xface.update_uv(vertex, xface.get_uv(vertex) + Vector((0.0, pixel_2d_size * amount)))

    if clockwise:
        _adjust_vertices_recursive(xface, pixel_2d_size, xface.get_index(vertex - 1), vertex_remaining - 1, clockwise,
                                   amount, horizontally)
    else:
        _adjust_vertices_recursive(xface, pixel_2d_size, xface.get_index(vertex + 1), vertex_remaining - 1, clockwise,
                                   amount, horizontally)


def snap_face_uv_to_pixel(xface: XFace, selection_only: bool, pixel_2d_size: float):
    if not selection_only or xface.get_face().select:
        for index in range(xface.get_face_length()):
            xface.update_uv(index, _snap_to_pixel(xface.get_uv(index), pixel_2d_size))


def _snap_to_pixel(point: Vector, pixel_2d_size: float, from_point: Vector = None):
    if from_point is None:
        x_reverse: bool = False
        y_reverse: bool = False
    else:
        x_reverse: bool = (point - from_point).x < 0
        y_reverse: bool = (point - from_point).y < 0

    point.x = _snap_with_multiplier(point.x, x_reverse, pixel_2d_size)
    point.y = _snap_with_multiplier(point.y, y_reverse, pixel_2d_size)
    return point


def _snap_with_multiplier(value: float, reverse: bool, pixel_2d_size: float) -> float:
    if reverse:
        next_pixel_index = floor(value / pixel_2d_size)
        current_pixel_index = next_pixel_index + 1

        next_pixel_pos = next_pixel_index * pixel_2d_size
        current_pixel_pos = current_pixel_index * pixel_2d_size

        if value >= current_pixel_pos - (pixel_2d_size * multiplier):
            return current_pixel_pos
        else:
            return next_pixel_pos
    else:
        current_pixel_index = floor(value / pixel_2d_size)
        next_pixel_index = current_pixel_index + 1

        current_pixel_pos = current_pixel_index * pixel_2d_size
        next_pixel_pos = next_pixel_index * pixel_2d_size

        if value <= current_pixel_pos + (pixel_2d_size * multiplier):
            return current_pixel_pos
        else:
            return next_pixel_pos
