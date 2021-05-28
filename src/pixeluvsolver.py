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


def new_solve_face(xface: XFace, pixels_per_3d: int, pixel_2d_size: float):
    # Convert all edges to uv basis
    prom = 0.0
    for i in range(xface.get_face_length()):
        length_3d = xface.get_edge(i).length
        prom += get_length2d(length_3d, pixels_per_3d, pixel_2d_size) / length_3d
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


# OLD IMPLEMENTATION

def solve_face(xface: XFace, pixels_per_3d: int, pixel_2d_size: float):
    log(DEBUG, "Starting face solving for face: " + str(xface))
    solved_vertices = solve_first_vertices(xface, pixels_per_3d, pixel_2d_size)
    solve_remaining_vertices(xface, solved_vertices, pixels_per_3d, pixel_2d_size)
    xface.solve()
    log(DEBUG, "Solved face " + str(xface) + "!")
    if not xface.is_3d_and_uv_aligned():
        log(WARN, "But face " + str(xface) + " is not correctly aligned between 2d and 3d!")


def solve_first_vertices(xface: XFace, pixels_per_3d: int, pixel_2d_size: float) -> Set[int]:
    has_aligned_edges = xface.has_any_aligned_edges()
    if xface.has_any_solved_neighbor(on_aligned_edges=has_aligned_edges):
        solved_neighbors = sorted(xface.get_solved_neighbors(on_aligned_edges=has_aligned_edges),
                                  key=lambda sorting_xface: sorting_xface.get_score(), reverse=True)
        return stitch_xface_to_neighbor(xface, solved_neighbors[0])

    if has_aligned_edges:
        return solve_by_aligned_edge(xface, pixels_per_3d, pixel_2d_size)

    return solve_by_basis_converted_edge(xface, pixels_per_3d, pixel_2d_size)


def stitch_xface_to_neighbor(xface: XFace, neighbor: XFace) -> Set[int]:
    log(DEBUG, "Face " + str(xface) + " will be stitched to neighbor face " + str(neighbor))
    solved_vertices = set()

    if xface.get_plane() == XFace.LATERAL and neighbor.get_plane() == XFace.LATERAL \
            and xface.is_inverted_against(neighbor):
        log(DEBUG, "The xface " + str(xface) + " is inverted!")
        xface.invert()

    common_edges = xface.get_common_edges(neighbor)
    log(DEBUG, "The common edges are: " + str(common_edges))
    for common_edge in common_edges:
        xface_start_vertex = common_edge[0]
        xface_next_vertex = xface.get_index(xface_start_vertex + 1)
        other_start_vertex = common_edge[1]
        other_next_vertex = neighbor.get_index(other_start_vertex + 1)

        log(DEBUG, "Vertex " + str(xface_start_vertex) + " will be assigned the uv from neighbor face vertex index "
            + str(other_next_vertex))
        xface.update_uv(xface_start_vertex, neighbor.get_uv(other_next_vertex))
        log(DEBUG, "Vertex " + str(xface_next_vertex) + " will be assigned the uv from neighbor face vertex index "
            + str(other_start_vertex))
        xface.update_uv(xface_next_vertex, neighbor.get_uv(other_start_vertex))

        solved_vertices.add(xface_start_vertex)
        solved_vertices.add(xface_next_vertex)
    return solved_vertices


def solve_by_aligned_edge(xface: XFace, pixels_per_3d: int, pixel_2d_size: float) -> Set[int]:
    log(DEBUG, "Face " + str(xface) + " will have its first vertices solved by one of its aligned edges")
    horizontal_edges = xface.get_horizontal_edges()
    vertical_edges = xface.get_vertical_edges()

    best_edge = get_best_scored_edge(xface, pixels_per_3d, horizontal_edges + vertical_edges)
    log(DEBUG, "Best aligned edge is " + str(best_edge))

    start_vertex = xface.get_index(best_edge)
    next_vertex = xface.get_index(start_vertex + 1)
    xface.update_uv(start_vertex, snap_to_pixel(Vector((0.0, 0.0)), pixel_2d_size))

    edge = xface.get_edge(start_vertex)
    if best_edge in horizontal_edges:
        log(DEBUG, "Best edge is horizontal, next vertex " + str(next_vertex) + " will be adjusted horizontally")
        x_sign = sign(xface.get_basis_converted_edge(start_vertex).x)
        length_2d = get_length2d(edge.length, pixels_per_3d, pixel_2d_size) * x_sign
        xface.update_uv(next_vertex, snap_to_pixel(Vector((length_2d, 0.0)), pixel_2d_size, xface.get_uv(start_vertex)))
    elif best_edge in vertical_edges:
        log(DEBUG, "Best edge is vertical, next vertex " + str(next_vertex) + " will be adjusted vertically")
        y_sign = sign(xface.get_basis_converted_edge(start_vertex).y)
        length_2d = get_length2d(edge.length, pixels_per_3d, pixel_2d_size) * y_sign
        xface.update_uv(next_vertex, snap_to_pixel(Vector((0.0, length_2d)), pixel_2d_size, xface.get_uv(start_vertex)))
    else:
        log(ERROR, "Impossible case, best edge is neither horizontal nor vertical")
        raise Exception("Critical error getting best aligned edge")
    return {start_vertex, next_vertex}


def get_best_scored_edge(xface: XFace, pixels_per_3d: int, all_edges: int) -> int:
    best_edge_score = None
    best_edge = None
    for edge_index in all_edges:
        edge = xface.get_edge(edge_index)
        score = get_distance_to_closest_3d_pixel(edge, pixels_per_3d)
        if best_edge_score is None or best_edge_score > score:
            best_edge_score = score
            best_edge = edge_index
    return best_edge


def get_distance_to_closest_3d_pixel(vector: Vector, pixels_per_3d: int) -> float:
    length = vector.length
    one_pixel_3d = 1 / pixels_per_3d
    pix_min_idx = int(length / one_pixel_3d)
    pix_max_idx = pix_min_idx + 1

    pix_min = pix_min_idx * one_pixel_3d
    pix_max = pix_max_idx * one_pixel_3d
    half_point = pix_min + (multiplier * one_pixel_3d)

    if length > half_point:
        return abs(pix_max - length)
    else:
        return abs(pix_min - length)


def solve_by_basis_converted_edge(xface: XFace, pixels_per_3d: int, pixel_2d_size: float) -> Set[int]:
    log(DEBUG, "Face " + str(xface) + " has no aligned edges nor solved neighbors, the first vertices will be deducted"
        + " using normal/up basis conversion on its vertices")
    xface.update_uv(xface.get_index(0), snap_to_pixel(Vector((0.0, 0.0)), pixel_2d_size))

    length2d = get_length2d(xface.get_edge(0).length, pixels_per_3d, pixel_2d_size)

    next_vertex_uv_position: Vector = xface.get_basis_converted_edge(0).to_2d().normalized() * length2d
    xface.update_uv(1, snap_to_pixel(next_vertex_uv_position, pixel_2d_size, xface.get_uv(0)))
    return {0, 1}


def solve_remaining_vertices(xface: XFace, solved_vertices: set, pixels_per_3d: int, pixel_2d_size: float):
    log(DEBUG, "Face " + str(xface) + " has already solved the following vertices " + str(solved_vertices)
        + ". Starting loop to solve remaining vertices")
    while len(solved_vertices) < xface.get_face_length():
        next_index = get_next_remaining_vertex_index(xface, solved_vertices)
        log(DEBUG, "Next vertex to solve is " + str(next_index))

        if xface.get_index(next_index - 1) in xface.get_horizontal_edges():
            solved_uv = solve_position_horizontally(xface, next_index, pixels_per_3d, pixel_2d_size)
        elif xface.get_index(next_index - 1) in xface.get_vertical_edges():
            solved_uv = solve_position_vertically(xface, next_index, pixels_per_3d, pixel_2d_size)
        else:
            solved_uv = solve_position_by_basis_converted(xface, next_index, pixels_per_3d, pixel_2d_size)

        prev_index = xface.get_index(next_index - 1)
        xface.update_uv(next_index, snap_to_pixel(solved_uv, pixel_2d_size, xface.get_uv(prev_index)))
        solved_vertices.add(next_index)
        log(DEBUG, "Solved vertices " + str(solved_vertices))


def get_next_remaining_vertex_index(xface: XFace, solved_vertices: set) -> int:
    next_index = min(solved_vertices)
    while next_index in solved_vertices:
        next_index = xface.get_index(next_index + 1)
    return next_index


def solve_position_horizontally(xface: XFace, index: int, pixels_per_3d: int, pixel_2d_size: float) -> Vector:
    log(DEBUG, "Position for vertex " + str(index) + " will be solved horizontally")
    prev_index = xface.get_index(index - 1)
    edge = xface.get_edge(prev_index)

    horizontal_sign = sign(xface.get_basis_converted_edge(prev_index).x)
    if horizontal_sign == 0:
        log(ERROR, "The sign for an horizontal edge cannot be zero! Check for duplicate vertices!")
        raise Exception("ERROR! Check for duplicate vertices!")
    length_2d = get_length2d(edge.length, pixels_per_3d, pixel_2d_size) * horizontal_sign

    uv_vec = Vector((length_2d, 0.0))
    return xface.get_uv(prev_index) + uv_vec


def solve_position_vertically(xface: XFace, index: int, pixels_per_3d: int, pixel_2d_size: float) -> Vector:
    log(DEBUG, "Position for vertex " + str(index) + " will be solved vertically")
    prev_index = xface.get_index(index - 1)
    edge = xface.get_edge(prev_index)

    vertical_sign = sign(xface.get_basis_converted_edge(prev_index).y)
    if vertical_sign == 0:
        log(ERROR, "The sign for an vertical edge cannot be zero! Check for duplicate vertices!")
        raise Exception("ERROR! Check for duplicate vertices!")
    length_2d = get_length2d(edge.length, pixels_per_3d, pixel_2d_size) * vertical_sign

    uv_vec = Vector((0.0, length_2d))
    return xface.get_uv(prev_index) + uv_vec


def solve_position_by_basis_converted(xface: XFace, index: int, pixels_per_3d: int, pixel_2d_size: float) -> Vector:
    log(DEBUG, "Position for vertex " + str(index) + " will be solved using the normal/up basis conversion")
    prev_index = xface.get_index(index - 1)
    length_2d = get_length2d(xface.get_edge(prev_index).length, pixels_per_3d, pixel_2d_size)

    vec_target_norm: Vector = xface.get_basis_converted_edge(prev_index).to_2d().normalized()
    vec_target: Vector = vec_target_norm * length_2d
    solved_uv: Vector = xface.get_uv(prev_index) + vec_target
    return solved_uv


def get_length2d(length3d: float, pixels_per_3d: int, pixel_2d_size: float):
    length2d: float = (pixels_per_3d * length3d) * pixel_2d_size
    return length2d


def snap_to_pixel(point: Vector, pixel_2d_size: float, from_point: Vector = None):
    if from_point is None:
        x_reverse: bool = False
        y_reverse: bool = False
    else:
        x_reverse: bool = (point - from_point).x < 0
        y_reverse: bool = (point - from_point).y < 0

    point.x = snap_with_multiplier(point.x, x_reverse, pixel_2d_size)
    point.y = snap_with_multiplier(point.y, y_reverse, pixel_2d_size)
    return point


def snap_with_multiplier(value: float, reverse: bool, pixel_2d_size: float) -> float:
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


# This method might not be required on this file
def snap_face_uv_to_pixel(xface: XFace, selection_only: bool, pixel_2d_size: float):
    if not selection_only or xface.get_face().select:
        for index in range(xface.get_face_length()):
            xface.update_uv(index, snap_to_pixel(xface.get_uv(index), pixel_2d_size))
