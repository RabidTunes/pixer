from math import sqrt
from typing import Tuple, List

import bmesh
import bpy
from bmesh.types import BMesh

from .facestitcher import stitch, StitchingError, stitch_by_vertex
from .pixeluvsolver import *


class PixelTexturizerOperator(bpy.types.Operator):
    bl_label = "PIXX"
    bl_idname = "rabid.pixel_texturizer"

    # Default values
    pixels_per_3d_unit = 10
    pixel_2d_size = 1.0 / 32.0
    only_selection = True
    separate_by_plane = True

    def execute(self, context):
        scene = context.scene
        pixel_texturizer = scene.pixel_texturizer
        try:
            self.run(context, pixel_texturizer.pixels_in_3D_unit, pixel_texturizer.texture_size,
                     pixel_texturizer.selection_only)
            self.report({'INFO'}, "All ok!")
        except Exception as exception:
            self.report({'ERROR'}, str(exception))
        return {'FINISHED'}

    def run(self, context, pixels_in_3d_unit, texture_size, selection_only):
        log(INFO, "Starting texture pixelation!")
        self.pixels_per_3d_unit = pixels_in_3d_unit
        self.pixel_2d_size = 1.0 / float(texture_size)
        self.only_selection = selection_only

        log(INFO, "Loading model data...")
        obj = context.active_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        uv_layer = bm.loops.layers.uv.verify()
        XFace.init(uv_layer)

        log(INFO, "Validating model...")
        self._validate(bm)

        log(INFO, "Parsing faces...")
        top, lateral, down = self._get_xfaces(bm)

        log(INFO, "Solving faces...")
        if self.separate_by_plane:
            uv_islands = self._solve(lateral)
            uv_islands = self._solve(top, uv_islands)
            self._solve(down, uv_islands)
        else:
            self._solve(lateral + top + down)

        log(INFO, "Packing UVs...")
        self._pack_together(context, selection_only)

        log(INFO, "Snapping packed UVs to pixel again...")
        for xface in lateral + top + down:
            snap_face_uv_to_pixel(xface, selection_only, self.pixel_2d_size)
        bmesh.update_edit_mesh(me)

    def _validate(self, bm: BMesh):
        vertices = set()
        for vert in bm.verts:
            if vert.co.copy().freeze() in vertices:
                log(ERROR, "The vert " + str(vert.co.copy().freeze()) + " is already in the set, "
                                                                        "it is probably a duplicate!")
            vertices.add(vert.co.copy().freeze())

        if len(bm.verts) != len(vertices):
            raise Exception("There are duplicated vertices! Cannot proceed!")

    def _get_xfaces(self, bm: BMesh):
        lateral_xfaces = []
        top_xfaces = []
        down_xfaces = []
        for face in bm.faces:
            if not self.only_selection or face.select:
                new_xface = XFace(face)
                if new_xface.get_plane() == XFace.LATERAL:
                    lateral_xfaces.append(new_xface)
                elif new_xface.get_plane() == XFace.TOP:
                    top_xfaces.append(new_xface)
                else:
                    down_xfaces.append(new_xface)
        log(DEBUG, "Lateral faces: " + str(len(lateral_xfaces)))
        for xface in lateral_xfaces:
            log(DEBUG, xface)
        log(DEBUG, "Top faces: " + str(len(top_xfaces)))
        for xface in top_xfaces:
            log(DEBUG, xface)
        log(DEBUG, "Down faces: " + str(len(down_xfaces)))
        for xface in down_xfaces:
            log(DEBUG, xface)
        return top_xfaces, lateral_xfaces, down_xfaces

    def _solve(self, all_faces: [XFace], uv_islands_by_xface=None):
        if uv_islands_by_xface is None:
            uv_islands_by_xface = {}
        for xface in all_faces:
            if not xface.solved():
                next_xfaces = [xface]
                while len(next_xfaces) > 0:
                    current = next_xfaces.pop(0)
                    log(DEBUG, "Solving face " + str(current))
                    new_solve_face(current, self.pixels_per_3d_unit, self.pixel_2d_size)

                    stitched = False
                    linked_solved, linked_unsolved = self._get_linked_faces_for(current)
                    linked_edge_solved = []
                    for linked in linked_solved:
                        if current.get_common_edges(linked):
                            linked_edge_solved.append(linked)

                    linked_vertex_solved = []
                    for linked in linked_solved:
                        if linked not in linked_edge_solved:
                            linked_vertex_solved.append(linked)

                    linked_edge_unsolved = []
                    for linked in linked_unsolved:
                        if current.get_common_edges(linked):
                            linked_edge_unsolved.append(linked)

                    for linked in linked_edge_solved:
                        try:
                            log(DEBUG, "Stitching face " + str(current) + " to near linked face " + str(linked))
                            stitch(current, linked, uv_islands_by_xface[linked.get_face()])
                        except StitchingError as error:
                            log(DEBUG, "The face " + str(current) + " cannot be stitched to " + str(linked)
                                + " because of " + str(error))
                        except Exception as error:
                            log(ERROR, "Unexpected exception " + str(error))
                            raise error
                        else:
                            log(DEBUG, "Face " + str(current) + " was stitched to face " + str(linked))
                            uv_islands_by_xface[linked.get_face()].append(current)
                            uv_islands_by_xface[current.get_face()] = uv_islands_by_xface[linked.get_face()]
                            stitched = True
                            break

                    if not stitched and linked_vertex_solved and not linked_edge_unsolved:
                        log(DEBUG, "Failed to stitch face by edge to near solved faces, trying to stitch it by vertex")
                        for linked in linked_vertex_solved:
                            try:
                                log(DEBUG, "Stitching face " + str(current) + " to near linked face " + str(linked))
                                stitch_by_vertex(current, linked, uv_islands_by_xface[linked.get_face()])
                            except StitchingError as error:
                                log(DEBUG, "The face " + str(current) + " cannot be stitched to " + str(linked)
                                    + " because of " + str(error))
                            except Exception as error:
                                log(ERROR, "Unexpected exception " + str(error))
                                raise error
                            else:
                                log(DEBUG, "Face " + str(current) + " was stitched to face " + str(linked))
                                uv_islands_by_xface[linked.get_face()].append(current)
                                uv_islands_by_xface[current.get_face()] = uv_islands_by_xface[linked.get_face()]
                                stitched = True
                                break

                    if not stitched:
                        log(DEBUG, "Face " + str(current) + " was not stitched to any near solved faces")
                        uv_islands_by_xface[current.get_face()] = [current]

                    log(DEBUG, "Detected near unsolved faces")
                    for n in linked_unsolved:
                        log(DEBUG, str(n))

                    for linked in linked_unsolved:
                        if linked not in next_xfaces:
                            if not self.separate_by_plane or linked.get_plane() == current.get_plane():
                                next_xfaces.append(linked)

                    next_xfaces = sorted(next_xfaces, key=lambda sorting_xface: sorting_xface.get_score(), reverse=True)
                    if next_xfaces:
                        log(DEBUG, "Next near xfaces to solve and stitch")
                        for n in next_xfaces:
                            log(DEBUG, str(n))
        return uv_islands_by_xface

    def _get_linked_faces_for(self, xface: XFace) -> Tuple[List[XFace], List[XFace]]:
        linked_solved = set()
        linked_unsolved = set()
        for linked_xface in xface.get_linked_xfaces():
            if not self.only_selection or linked_xface.get_face().select:
                if linked_xface.solved():
                    linked_solved.add(linked_xface)
                else:
                    linked_unsolved.add(linked_xface)
        return list(linked_solved), list(linked_unsolved)

    def _pack_together(self, context, selection_only):
        prev_area_type = bpy.context.area.type
        prev_ui_type = bpy.context.area.ui_type
        bpy.context.area.type = 'IMAGE_EDITOR'
        bpy.context.area.ui_type = 'UV'
        obj = context.active_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        uv_layer = bm.loops.layers.uv.verify()
        pivot_ori = bpy.context.space_data.pivot_point

        uv_verts = []
        c = 0

        for face in bm.faces:
            if not selection_only or face.select:
                for loop in face.loops:
                    luv = loop[uv_layer]
                    luv.select = True
                    if luv.select and luv.uv not in uv_verts and c != 2:
                        uv_verts.append(luv.uv)
                        c += 1

        if len(uv_verts) == 2:
            distance = sqrt((uv_verts[0].x - uv_verts[1].x) ** 2 + (uv_verts[0].y - uv_verts[1].y) ** 2)

            bpy.ops.uv.pack_islands(rotate=False, margin=0.05)

            distance2 = sqrt((uv_verts[0].x - uv_verts[1].x) ** 2 + (uv_verts[0].y - uv_verts[1].y) ** 2)

            scale = distance / distance2
            bpy.context.space_data.pivot_point = 'CURSOR'
            bpy.ops.uv.cursor_set(location=(0, 0))
            bpy.ops.uv.select_linked()
            bpy.ops.transform.resize(value=(scale, scale, scale), orient_type='GLOBAL',
                                     orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL',
                                     mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH',
                                     proportional_size=1, use_proportional_connected=False,
                                     use_proportional_projected=False)
            bpy.context.space_data.pivot_point = '' + pivot_ori + ''
            bpy.context.area.type = prev_area_type
            bpy.context.area.ui_type = prev_ui_type
        else:
            self.report({"ERROR"}, "Error while packing UVs. No island selected")

    def _old_solve(self, xfaces_lists):
        me = None
        solved_faces = set()
        uv_islands = []
        facecount = 0
        facemax = 3
        for xface_list in xfaces_lists:
            for xface in xface_list:
                if not xface.get_face() in solved_faces:
                    new_uv_island = []
                    processing_xfaces = [xface]
                    while len(processing_xfaces) > 0:
                        current_xface = processing_xfaces.pop(0)
                        new_solve_face(current_xface, self.pixels_per_3d_unit, self.pixel_2d_size)
                        facecount += 1
                        solved_faces.add(current_xface.get_face())
                        new_uv_island.append(current_xface.get_face())
                        linked_xfaces = current_xface.get_linked_xfaces()
                        for linked_xface in linked_xfaces:
                            if not self.only_selection or linked_xface.get_face().select:
                                if not (linked_xface.get_face() in solved_faces or linked_xface in processing_xfaces):
                                    if linked_xface.get_plane() == xface.get_plane():
                                        processing_xfaces.append(linked_xface)
                        processing_xfaces = sorted(processing_xfaces,
                                                   key=lambda sorting_xface: sorting_xface.get_score(),
                                                   reverse=True)
                        log(DEBUG, "After solving, these are the processing xfaces")
                        for p in processing_xfaces:
                            log(DEBUG, str(p))
                        if facecount >= facemax > 0:
                            bmesh.update_edit_mesh(me)
                            raise Exception
                    uv_islands.append(new_uv_island)
