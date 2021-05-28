from __future__ import annotations

from typing import List, Tuple

from .logger import *
from .utils import *
from mathutils import Matrix, Vector
from math import radians
from bmesh.types import BMFace


#################
# XFACE CLASS ##
#################
# This class is just a wrapper for the default blender BMFace class to add
# some sugar on it
class XFace:
    # Common
    UP_VEC = Vector((0.0, 0.0, 1.0))
    DOWN_VEC = -UP_VEC
    MIN_VERTICAL_ANGLE = 30
    LATERAL = 0
    TOP = 1
    DOWN = 2
    ALL_XFACES = {}
    UV_LAYER = None

    # Variables of each object
    face: BMFace = None
    is_solved = False
    plane = None
    horizontal_edges = []
    vertical_edges = []
    inverted = False

    def init(uv_layer):  # Check this warning later
        XFace.UV_LAYER = uv_layer

    def get_face(self) -> BMFace:
        return self.face

    def get_face_length(self) -> int:
        return len(self.face.loops)

    def get_index(self, index) -> int:
        while index < 0:
            index += self.get_face_length()
        return index % self.get_face_length()

    def get_plane(self) -> int:
        return self.plane

    def get_plane_string(self) -> str:
        if self.plane == XFace.LATERAL:
            return "LATERAL"
        elif self.plane == XFace.TOP:
            return "TOP"
        else:
            return "DOWN"

    def get_vertex(self, index: int) -> Vector:
        index = self.get_index(index)
        return self.face.loops[index].vert.co.copy()

    def get_edge(self, index: int) -> Vector:
        return self.get_vertex(self.get_index(index + 1)) - self.get_vertex(self.get_index(index))

    def get_score(self) -> float:
        return len(self.get_solved_neighbors()) + (len(self.horizontal_edges) + len(self.vertical_edges)) / len(self.face.loops)

    def get_uv(self, index: int) -> Vector:
        return self.face.loops[self.get_index(index)][XFace.UV_LAYER].uv.copy()

    def get_all_uvs(self) -> [Vector]:
        all_uvs = []
        for i in range(self.get_face_length()):
            all_uvs.append(self.get_uv(i))
        return all_uvs

    def get_uv_edge(self, index: int) -> Vector:
        return self.get_uv(index + 1) - self.get_uv(index)

    def get_uv_horizontal_aligned(self) -> []:
        result = []
        for i in range(self.get_face_length()):
            if self.get_uv(i + 1).y == self.get_uv(i).y:
                result.append(i)
        return result

    def get_uv_vertical_aligned(self) -> []:
        result = []
        for i in range(self.get_face_length()):
            if self.get_uv(i + 1).x == self.get_uv(i).x:
                result.append(i)
        return result

    def is_3d_and_uv_aligned(self) -> bool:
        if not self.get_horizontal_edges() and not self.get_vertical_edges():
            return True
        else:
            hor_3d = sorted(self.get_horizontal_edges())
            ver_3d = sorted(self.get_vertical_edges())
            hor_2d = sorted(self.get_uv_horizontal_aligned())
            ver_2d = sorted(self.get_uv_vertical_aligned())
            log(DEBUG, "Horizontal 3d edges " + str(hor_3d), ["3d2dalign"])
            log(DEBUG, "Vertical 3d edges " + str(ver_3d), ["3d2dalign"])
            log(DEBUG, "Horizontal 2d edges " + str(hor_2d), ["3d2dalign"])
            log(DEBUG, "Vertical 2d edges " + str(ver_2d), ["3d2dalign"])
            return all(elem in hor_2d for elem in hor_3d) and all(elem in ver_2d for elem in ver_3d)

    def update_uv(self, index: int, new_uv: Vector):
        index = self.get_index(index)
        self.face.loops[index][XFace.UV_LAYER].uv = new_uv

    def get_linked_xfaces(self) -> List[XFace]:
        linked_faces = [f for e in self.face.verts for f in e.link_faces if f is not self.face]
        linked_xfaces = []
        for linked_face in linked_faces:
            if linked_face not in XFace.ALL_XFACES:
                XFace.ALL_XFACES[linked_face] = XFace(linked_face)
            linked_xfaces.append(XFace.ALL_XFACES[linked_face])
        return linked_xfaces

    def get_horizontal_edges(self) -> []:
        return self.horizontal_edges

    def get_vertical_edges(self) -> []:
        return self.vertical_edges

    def has_any_aligned_edges(self) -> bool:
        return bool(self.horizontal_edges or self.vertical_edges)

    def get_solved_neighbors(self, on_aligned_edges=False) -> List[XFace]:
        solved_neighbors_by_edge = []
        solved_neighbors = [linked_xface for linked_xface in self.get_linked_xfaces() if linked_xface.solved()
                            and linked_xface.get_plane() == self.get_plane()]
        for neighbor in solved_neighbors:
            common_edges = self.get_common_edges(neighbor)
            for edge_tuple in common_edges:
                self_edge = edge_tuple[0]
                if not on_aligned_edges or (self_edge in self.get_horizontal_edges()) \
                        or (self_edge in self.get_vertical_edges()):
                    solved_neighbors_by_edge.append(neighbor)
        return solved_neighbors_by_edge

    def has_any_solved_neighbor(self, on_aligned_edges=False) -> bool:
        return bool(self.get_solved_neighbors_by_edge(on_aligned_edges))

    def get_solved_neighbors_by_edge(self, on_aligned_edges=False) -> List[Tuple[int, XFace]]:
        solved_neighbors_by_edge = []
        solved_neighbors = self.get_solved_neighbors()
        for neighbor in solved_neighbors:
            common_edges = self.get_common_edges(neighbor)
            for edge_tuple in common_edges:
                self_edge = edge_tuple[0]
                if not on_aligned_edges or (self_edge in self.get_horizontal_edges()) \
                        or (self_edge in self.get_vertical_edges()):
                    solved_neighbors_by_edge.append((self_edge, neighbor))
        return solved_neighbors_by_edge

    def is_inverted_against(self, other: XFace) -> bool:
        common_edges = self.get_common_edges(other)
        for common_edge in common_edges:
            self_edge = self.get_edge(common_edge[0]).normalized()
            other_edge = other.get_edge(common_edge[1]).normalized()
            self_basis_edge = self.get_basis_converted_edge(common_edge[0]).normalized()
            other_basis_edge = other.get_basis_converted_edge(common_edge[1]).normalized()

            if equals_sign(self_edge, -other_edge) and equals_sign(self_basis_edge, other_basis_edge):
                return True
        return False

    def invert(self):
        self.inverted = not self.inverted

    def is_inverted(self) -> bool:
        return self.inverted

    def solve(self):
        self.is_solved = True

    def solved(self) -> bool:
        return self.is_solved

    def get_common_vertices(self, other: XFace):
        log(DEBUG,
            "Finding common vertices between " + str(self.get_face().index) + " and " + str(other.get_face().index),
            ["matching"])
        common_vertices = []
        for i in range(self.get_face_length()):
            for j in range(other.get_face_length()):
                if self.get_vertex(i) == other.get_vertex(j):
                    common_vertices.append((i, j))

        log(DEBUG, "Common vertices\n" + str(common_vertices) + "\n", ["matching"])
        for v in common_vertices:
            log(DEBUG, str(v) + "///" + str(self.get_vertex(v[0])), ["matching"])
            log(DEBUG, str(v) + "///" + str(other.get_vertex(v[1])), ["matching"])
            log(DEBUG, "###", ["matching"])
        return common_vertices

    def get_common_edges(self, other: XFace):
        common_edges = []
        common_vertices = self.get_common_vertices(other)
        self_vertices = []
        other_vertices = []
        for vertex_tuple in common_vertices:
            self_vertices.append(vertex_tuple[0])
            other_vertices.append(vertex_tuple[1])

        for vertex_tuple in common_vertices:
            if self.get_index(vertex_tuple[0] + 1) in self_vertices:
                common_edges.append((vertex_tuple[0], other.get_index(vertex_tuple[1] - 1)))

        for v in common_edges:
            log(DEBUG, str(v) + "///" + str(self.get_edge(v[0])), ["matching"])
            log(DEBUG, str(v) + "///" + str(other.get_edge(v[1])), ["matching"])
            log(DEBUG, "###", ["matching"])
        return common_edges

    def get_basis_converted_vertex(self, index) -> Vector:
        normal = self.face.normal.normalized()
        # normal = self.get_vertex_normal(index).normalized()
        if self.plane == XFace.LATERAL:
            up = Vector((0.0, 0.0, 1.0))
        elif self.plane == XFace.TOP:
            up = Vector((0.0, 1.0, 0.0))
        else:
            up = Vector((0.0, -1.0, 0.0))
        if self.is_inverted():
            up = -up
        basis_ihat = up.normalized().cross(normal).normalized()
        basis_jhat = normal.cross(basis_ihat).normalized()
        basis_khat = normal

        basis = Matrix().to_3x3()
        basis[0][0], basis[1][0], basis[2][0] = basis_ihat[0], basis_ihat[1], basis_ihat[2]
        basis[0][1], basis[1][1], basis[2][1] = basis_jhat[0], basis_jhat[1], basis_jhat[2]
        basis[0][2], basis[1][2], basis[2][2] = basis_khat[0], basis_khat[1], basis_khat[2]

        inv_basis = basis.inverted()
        return inv_basis @ self.get_vertex(index)

    def get_basis_converted_edge(self, index) -> Vector:
        return self.get_basis_converted_vertex(index + 1) - self.get_basis_converted_vertex(index)

    def get_vertex_normal(self, index) -> Vector:
        a = self.get_vertex(index + 1) - self.get_vertex(index)
        b = self.get_vertex(index - 1) - self.get_vertex(index)
        return a.cross(b)

    def _calculate_plane(self):
        if self.face.normal.angle(XFace.UP_VEC) <= radians(XFace.MIN_VERTICAL_ANGLE):
            self.plane = XFace.TOP
        elif self.face.normal.angle(XFace.DOWN_VEC) <= radians(XFace.MIN_VERTICAL_ANGLE):
            self.plane = XFace.DOWN
        else:
            self.plane = XFace.LATERAL
        log(DEBUG, "Plane for " + str(self.face.index) + " is " + str(self.get_plane_string()), ["init"])

    def _calculate_edges_alignment(self):
        if self.plane == XFace.LATERAL:
            for i in range(len(self.face.loops)):
                curr_v = self.get_vertex(i)
                next_v = self.get_vertex(i + 1)
                if curr_v.z == next_v.z:
                    self.horizontal_edges.append(i)
                if curr_v.x == next_v.x and curr_v.y == next_v.y:
                    self.vertical_edges.append(i)
        else:
            for i in range(len(self.face.loops)):
                curr_v = self.get_vertex(i)
                next_v = self.get_vertex(i + 1)
                if curr_v.y == next_v.y:
                    self.horizontal_edges.append(i)
                if curr_v.x == next_v.x:
                    self.vertical_edges.append(i)
        log(DEBUG, "Horizontal edges in face " + str(self.face.index) + " are " + str(self.horizontal_edges), ["init"])
        log(DEBUG, "Vertical edges in face " + str(self.face.index) + " are " + str(self.vertical_edges), ["init"])

    def __init__(self, face: BMFace):
        log(DEBUG, "Creating XFace for " + str(face.index), ["init"])
        self.is_solved = False
        self.horizontal_edges = []
        self.vertical_edges = []
        self.face = face
        self._calculate_plane()
        self._calculate_edges_alignment()
        XFace.ALL_XFACES[face] = self

    def __eq__(self, other):
        if other is None:
            return False
        return self.get_face() == other.get_face()

    def __hash__(self):
        return self.get_face().__hash__()

    def __ne__(self, other):
        if other is None:
            return True
        return self.get_face() != other.get_face()

    def __str__(self):
        return "XFACE(" + str(self.face.index) + ", " + self.get_plane_string() + ")"
