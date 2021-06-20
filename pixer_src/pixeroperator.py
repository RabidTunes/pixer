import bmesh
import bpy
from typing import Tuple, List, Dict
from bmesh.types import BMesh, BMFace
from .benchmarker import print_bench, bench_start, bench_end
from .facestitcher import stitch, StitchingError, stitch_by_vertex
from .pixeluvsolver import *
from .uvpacker import simple_uv_packing
from .validator import validate


class PixerOperator(bpy.types.Operator):
    bl_label = "Pixer"
    bl_idname = "rabid.pixer"

    # Default values
    pixels_per_3d_unit = 10
    pixel_2d_size = 1.0 / 32.0
    only_selection = True
    separate_by_plane = True

    def execute(self, context):
        scene = context.scene
        pixer = scene.pixer
        try:
            self.run(context, pixer.pixels_in_3D_unit, pixer.texture_size,
                     pixer.selection_only)
            self.report({'INFO'}, "All ok!")
        except Exception as exception:
            self.report({'ERROR'}, str(exception))
        print_bench()
        return {'FINISHED'}

    def run(self, context, pixels_in_3d_unit, texture_size, selection_only):
        log(INFO, "Starting texture pixelation!")
        self.pixels_per_3d_unit = pixels_in_3d_unit
        self.pixel_2d_size = 1.0 / float(texture_size)
        self.only_selection = selection_only

        log(INFO, "Loading model data...")
        bench_start("Load model")
        obj = context.active_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        uv_layer = bm.loops.layers.uv.verify()
        XFace.init(uv_layer)
        bench_end("Load model")

        log(INFO, "Validating model...")
        validate(bm)

        log(INFO, "Parsing faces...")
        bench_start("Parse faces")
        top, lateral, down = self._get_xfaces(bm)
        bench_end("Parse faces")

        log(INFO, "Solving faces...")
        bench_start("Solve and stitch faces")
        if self.separate_by_plane:
            uv_islands_map = self._solve(lateral)
            uv_islands_map = self._solve(top, uv_islands_map)
            uv_islands_map = self._solve(down, uv_islands_map)
        else:
            uv_islands_map = self._solve(lateral + top + down)
        bench_end("Solve and stitch faces")

        log(INFO, "Packing UVs...")
        bench_start("UV Packing")
        simple_uv_packing(uv_islands_map, self.pixel_2d_size)

        log(INFO, "Snapping packed UVs to pixel again...")
        for xface in lateral + top + down:
            snap_face_uv_to_pixel(xface, selection_only, self.pixel_2d_size)
        bench_end("UV Packing")
        bmesh.update_edit_mesh(me)

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

    def _solve(self, all_faces: [XFace],
               uv_islands_by_xface: Dict[BMFace, List[XFace]] = None) -> Dict[BMFace, List[XFace]]:
        if uv_islands_by_xface is None:
            uv_islands_by_xface = {}
        for xface in all_faces:
            if not xface.solved():
                next_xfaces = [xface]
                while len(next_xfaces) > 0:
                    current = next_xfaces.pop(0)
                    log(DEBUG, "Solving face " + str(current))
                    bench_start("Solve face " + str(current.get_face().index), "Solve and stitch faces")
                    solve_face(current, self.pixels_per_3d_unit, self.pixel_2d_size)
                    bench_end("Solve face " + str(current.get_face().index), "Solve and stitch faces")

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

                    bench_start("Stitch face " + str(current.get_face().index), "Solve and stitch faces")
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
                    bench_end("Stitch face " + str(current.get_face().index), "Solve and stitch faces")

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
