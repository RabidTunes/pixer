import bpy 
import math
from mathutils import Matrix, Vector
import bmesh
from itertools import combinations

bl_info = {
	"name" : "Pixel Texturizer",
	"author" : "RabidTunes",
	"version" : (0, 9),
	"blender" : (2, 92, 0),
	"description" : "Adjusts the UVs from a model to set the textures to pixels",
	"wiki_url" : "",
	"category" : "UV"
}

################################################################
#################
## DEBUG UTILS ##
#################
TRACE = "TRACE"
DEBUG = "DEBUG"
INFO = "INFO"
WARN = "WARN"
ERROR = "ERROR"
active_log_level = DEBUG
log_levels = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR"]
active_log_tags = []

def log(level, text, tags = []):
	if active_log_level != None:
		if log_levels.index(level) >= log_levels.index(active_log_level):
			if not tags or all(elem in active_log_tags for elem in tags):
				print("[" + str(level) + "]" + str(tags) + " " + str(text))
################################################################


class PixelTexturizerProperties(bpy.types.PropertyGroup):
	pixels_in_3D_unit : bpy.props.IntProperty(name="Pixels per 3D unit", description="How many squares are inside a 3D unit (you can use ortographic view to check this)", default=10, min=1)
	texture_size : bpy.props.IntProperty(name="Texture Size", description="Size of texture. Assumes it is squared", default=32, min=1)
	selection_only : bpy.props.BoolProperty(name="Selection only", description="Check this if you want to apply the texturizer only to selected faces",default=False)   


class PixelTexturizerMainPanel(bpy.types.Panel):
	bl_label = "Pixel Texturizer"
	bl_idname = "PixelTexturizerMainPanel"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "Pixel Texturizer"

	def draw(self, context):
		layout = self.layout
		scene = context.scene
		pixel_texturizer = scene.pixel_texturizer
		
		layout.prop(pixel_texturizer, "pixels_in_3D_unit")
		layout.prop(pixel_texturizer, "texture_size")
		layout.prop(pixel_texturizer, "selection_only")

		row = layout.row()
		row.label(icon='WORLD_DATA')
		row.operator(text= "Pixelize!", operator="rabid.pixel_texturizer")
		row.label(icon='WORLD_DATA')

################################################################
## HELPER CLASSES ##
################################################################
#################
## XFACE CLASS ##
#################
# This class is just a wrapper for the default blender BMFace class to add
# some sugar on it. It provides methods that allow for example:
# - Knowing if the face has already been solved (adjusted to pixels)
# - Knowing if the face has some edges aligned to any planes (this helps us decide which face to solve first)
# - More stuff (TODO, ADD SOME COMMENTS HERE EXPLAINING MORE)
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
	face = None
	is_solved = False
	plane = None
	horizontal_edges = []
	vertical_edges = []
	
	def init(uv_layer):
		XFace.UV_LAYER = uv_layer
	
	def get_face(self):
		return self.face
	
	def get_face_length(self):
		return len(self.face.loops)
	
	def get_plane(self):
		return self.plane
	
	def get_plane_string(self):
		if self.plane == XFace.LATERAL:
			return "LATERAL"
		elif self.plane == XFace.TOP:
			return "TOP"
		else:
			return "DOWN"
	
	def get_vertex(self, index):
		return self.face.loops[(index + len(self.face.loops)) % len(self.face.loops)].vert.co.copy()
	
	def get_edge(self, index):
		return self.get_vertex(index + 1) - self.get_vertex(index)
	
	def get_score(self):
		return (len(self.horizontal_edges) + len(self.vertical_edges)) / len(self.face.loops)
	
	def get_uv(self, index):
		return self.face.loops[(index + len(self.face.loops)) % len(self.face.loops)][XFace.UV_LAYER].uv.copy()
	
	def get_uv_edge(self, index):
		return self.get_uv(index + 1) - self.get_uv(index)
	
	def get_uv_horizontal_aligned(self):
		result = []
		for i in range(self.get_face_length()):
			if self.get_uv(i + 1).y == self.get_uv(i).y:
				result.append(i)
		return result

	def get_uv_vertical_aligned(self):
		result = []
		for i in range(self.get_face_length()):
			if self.get_uv(i + 1).x == self.get_uv(i).x:
				result.append(i)
		return result
	
	def is_3d_and_uv_aligned(self):
		hor_3d = sorted(self.get_horizontal_edges())
		ver_3d = sorted(self.get_vertical_edges())
		hor_2d = sorted(self.get_uv_horizontal_aligned())
		ver_2d = sorted(self.get_uv_vertical_aligned())
		log(DEBUG, "Horizontal 3d edges " + str(hor_3d), ["3d2dalign"])
		log(DEBUG, "Vertical 3d edges " + str(ver_3d), ["3d2dalign"])
		log(DEBUG, "Horizontal 2d edges " + str(hor_2d), ["3d2dalign"])
		log(DEBUG, "Vertical 2d edges " + str(ver_2d), ["3d2dalign"])
		return all(elem in hor_2d for elem in hor_3d) and all(elem in ver_2d for elem in ver_3d)
		
	
	def update_uv(self, index, new_uv):
		self.face.loops[(index + len(self.face.loops)) % len(self.face.loops)][XFace.UV_LAYER].uv = new_uv
	
	def get_linked_xfaces(self):
		linked_faces = [f for e in self.face.edges for f in e.link_faces if f is not self.face]
		linked_xfaces = []
		for linked_face in linked_faces:
			new_xface = None
			if not linked_face in XFace.ALL_XFACES:
				new_xface = XFace(linked_face)
				XFace.ALL_XFACES[linked_face] = new_xface
			linked_xfaces.append(XFace.ALL_XFACES[linked_face])
		return linked_xfaces
	
	def get_horizontal_edges(self):
		return self.horizontal_edges
	
	def get_vertical_edges(self):
		return self.vertical_edges

	def get_topmost_horizontal_edge(self):
		if self.horizontal_edges:
			if self.plane == XFace.LATERAL:
				for index in self.horizontal_edges:
					found = True
					for i in range(self.get_face_length()):
						if self.get_vertex(i).z > self.get_vertex(index).z:
							# This is not topmost horizontal edge
							found = False
							break
					if found:
						return index
			elif self.plane == XFace.TOP:
				for index in self.horizontal_edges:
					found = True
					for i in range(self.get_face_length()):
						if self.get_vertex(i).y > self.get_vertex(index).y:
							# This is not topmost horizontal edge
							found = False
							break
					if found:
						return index
			else:
				for index in self.horizontal_edges:
					found = True
					for i in range(self.get_face_length()):
						if self.get_vertex(i).y < self.get_vertex(index).y:
							# This is not topmost horizontal edge
							found = False
							break
					if found:
						return index
		return None
	
	def get_botmost_horizontal_edge(self):
		if self.horizontal_edges:
			log(DEBUG, "hello")
			log(DEBUG, str(self.horizontal_edges))
			if self.plane == XFace.LATERAL:
				for index in self.horizontal_edges:
					found = True
					for i in range(self.get_face_length()):
						if self.get_vertex(i).z < self.get_vertex(index).z:
							log(DEBUG, "Index " + str(index) + " is not botmost because " + str(i) + " is bottommer")
							log(DEBUG, str(self.get_vertex(index)) + "//" + str(self.get_vertex(i)))
							found = False
							break
					if found:
						return index
			elif self.plane == XFace.TOP:
				for index in self.horizontal_edges:
					found = True
					for i in range(self.get_face_length()):
						if self.get_vertex(i).y < self.get_vertex(index).y:
							# This is not botmost horizontal edge
							found = False
							break
					if found:
						return index
			else:
				for index in self.horizontal_edges:
					found = True
					for i in range(self.get_face_length()):
						if self.get_vertex(i).y > self.get_vertex(index).y:
							# This is not botmost horizontal edge
							found = False
							break
					if found:
						return index
		return None	
	
	def get_rightmost_vertical_edge(self):
		if self.vertical_edges:
			if self.plane == XFace.LATERAL:
				for index in self.vertical_edges:
					if self.get_vertex(index).z < self.get_vertex(index + 1).y:
						return index
			else:
				for index in self.vertical_edges:
					if self.get_vertex(index).y < self.get_vertex(index + 1).y:
						return index
		return None
	
	def get_leftmost_vertical_edge(self):
		if self.vertical_edges:
			if self.plane == XFace.LATERAL:
				for index in self.vertical_edges:
					if self.get_vertex(index).z > self.get_vertex(index + 1).y:
						return index
			else:
				for index in self.vertical_edges:
					if self.get_vertex(index).y > self.get_vertex(index + 1).y:
						return index
		return None
	
	def get_topmost_vertex_index(self):
		index = 0
		if self.plane == XFace.LATERAL:
			current_up = self.get_vertex(index).z
			for i in range(self.get_face_length()):
				if current_up < self.get_vertex(i).z:
					index = i
					current_up = self.get_vertex(i).z
		elif self.plane == XFace.TOP:
			current_up = self.get_vertex(index).y
			for i in range(self.get_face_length()):
				if current_up < self.get_vertex(i).y:
					index = i
					current_up = self.get_vertex(i).y
		else:
			current_up = self.get_vertex(index).y
			for i in range(self.get_face_length()):
				if current_up > self.get_vertex(i).y:
					index = i
					current_up = self.get_vertex(i).y
		return index
	
	def solve(self):
		self.is_solved = True
	
	def solved(self):
		return self.is_solved
	
	def find_matching_vertices(self, other):
		log(DEBUG, "Finding matching vertices between " + str(self.get_face().index) + " and " + str(other.get_face().index), ["matching"])
		self_matching_vertices = []
		other_matching_vertices = []
		for i in range(self.get_face_length()):
			for j in range(other.get_face_length()):
				if self.get_vertex(i) == other.get_vertex(j):
					self_matching_vertices.append(i)
					other_matching_vertices.append(j)
		log(DEBUG, "Matching vertices\n" + str(self_matching_vertices) + "\n" + str(other_matching_vertices), ["matching"])
		
		for v in self_matching_vertices:
			log(DEBUG, str(v) + "///" + str(self.get_vertex(v)), ["matching"])
		log(DEBUG, "###", ["matching"])
		for v in other_matching_vertices:
			log(DEBUG, str(v) + "///" + str(other.get_vertex(v)), ["matching"])
		return ((self_matching_vertices, other_matching_vertices))

	def find_matching_edges(self, other):
		log(DEBUG, "Finding matching edges between " + str(self.get_face().index) + " and " + str(other.get_face().index), ["matching"])
		self_matching_edges = []
		other_matching_edges = []
		
		matching_vertices = self.find_matching_vertices(other)
		self_matching = matching_vertices[0]
		other_matching = matching_vertices[1]
		if len(self_matching) == 2:
			self_shared_edge = None
			if self_matching[0] == self_matching[1] - 1 or (self_matching[0] == (self.get_face_length() - 1) and self_matching[1] == 0):
				self_shared_edge = self_matching[0]
			elif self_matching[0] - 1 == self_matching[1] or (self_matching[1] == (self.get_face_length() - 1) and self_matching[0] == 0):
				self_shared_edge = self_matching[1]
			else:
				raise Exception("Mismatching shared vertices, they are not consecutive")
			
			other_shared_edge = None
			if other_matching[0] == other_matching[1] - 1 or (other_matching[0] == (other.get_face_length() - 1) and other_matching[1] == 0):
				other_shared_edge = other_matching[0]
			elif other_matching[0] - 1 == other_matching[1] or (other_matching[1] == (other.get_face_length() - 1) and other_matching[0] == 0):
				other_shared_edge = other_matching[1]
			else:
				raise Exception("Mismatching shared vertices, they are not consecutive")
				
			self_matching_edges.append(self_shared_edge)
			other_matching_edges.append(other_shared_edge)
		else:
			raise Exception("Two faces cannot share more than 2 vertices")
		log(DEBUG, "Matching edges\n" + str(self_matching_edges) + "\n" + str(other_matching_edges), ["matching"])
		return ((self_matching_edges, other_matching_edges))
	
	def find_matching_same_alignment_edges(self, other):
		log(DEBUG, "Finding matching aligned edges between " + str(self.get_face().index) + " and " + str(other.get_face().index), ["matching"])
		((self_matching_edges, other_matching_edges)) = self.find_matching_edges(other)
		self_matching_aligned_edges = []
		other_matching_aligned_edges = []
		log(DEBUG, "Horizontal edges for " + str(self.get_face().index), ["matching"])
		for hor in self.get_horizontal_edges():
			log(DEBUG, hor, ["matching"])
		log(DEBUG, "Vertical edges for " + str(self.get_face().index), ["matching"])
		for ver in self.get_vertical_edges():
			log(DEBUG, ver, ["matching"])
		log(DEBUG, "Horizontal edges for " + str(other.get_face().index), ["matching"])
		for hor in other.get_horizontal_edges():
			log(DEBUG, hor, ["matching"])
		log(DEBUG, "Vertical edges for " + str(other.get_face().index), ["matching"])
		for ver in other.get_vertical_edges():
			log(DEBUG, ver, ["matching"])
		
		
		for i in range(len(self_matching_edges)):
			self_horizontal = self_matching_edges[i] in self.get_horizontal_edges()
			other_horizontal = other_matching_edges[i] in other.get_horizontal_edges()
			self_vertical = self_matching_edges[i] in self.get_vertical_edges()
			other_vertical = other_matching_edges[i] in other.get_vertical_edges()
			
			if (self_horizontal and other_horizontal) or (self_vertical and other_vertical):
				self_matching_aligned_edges.append(self_matching_edges[i])
				other_matching_aligned_edges.append(other_matching_edges[i])
		
		log(DEBUG, "Matching aligned edges\n" + str(self_matching_aligned_edges) + "\n" + str(other_matching_aligned_edges), ["matching"])
		return ((self_matching_aligned_edges, other_matching_aligned_edges))
		
	def get_basis_converted_vertex(self, index):
		up = None
		if self.plane == XFace.LATERAL:
			up = Vector((0.0, 0.0, 1.0))
		elif self.plane == XFace.TOP:
			up = Vector((0.0, 1.0, 0.0))
		else:
			up = Vector((0.0, -1.0, 0.0))
		basis_ihat = up.normalized().cross(self.face.normal.normalized())
		basis_jhat = self.face.normal.normalized().cross(basis_ihat).normalized()
		basis_khat = self.face.normal.normalized()

		basis = Matrix().to_3x3()
		basis[0][0], basis[1][0], basis[2][0] = basis_ihat[0], basis_ihat[1], basis_ihat[2]
		basis[0][1], basis[1][1], basis[2][1] = basis_jhat[0], basis_jhat[1], basis_jhat[2]
		basis[0][2], basis[1][2], basis[2][2] = basis_khat[0], basis_khat[1], basis_khat[2]
		
		inv_basis = basis.inverted()
		return inv_basis @ self.get_vertex(index)

	def get_basis_converted_edge(self, index):
		return self.get_basis_converted_vertex(index + 1) - self.get_basis_converted_vertex(index)
	
	def __init__(self, face):
		log(DEBUG, "Creating XFace for " + str(face.index), ["init"])
		self.is_solved = False
		self.horizontal_edges = []
		self.vertical_edges = []
		self.face = face
		self._calculate_plane()
		self._calculate_edges_alignment()
		XFace.ALL_XFACES[face] = self
	
	def _calculate_plane(self):
		if self.face.normal.angle(XFace.UP_VEC) <= math.radians(XFace.MIN_VERTICAL_ANGLE):
			self.plane = XFace.TOP
		elif self.face.normal.angle(XFace.DOWN_VEC) <= math.radians(XFace.MIN_VERTICAL_ANGLE):
			self.plane = XFace.DOWN
		else:
			self.plane = XFace.LATERAL
		log(DEBUG, "Plane for " + str(self.face.index) + " is " + str(self.get_plane_string()), ["init"])
			
	def _calculate_edges_alignment(self):
		if self.plane == XFace.LATERAL:
			for i in range(len(self.face.loops)):
				curr = self.get_vertex(i)
				next = self.get_vertex(i + 1)
				if curr.z == next.z:
					self.horizontal_edges.append(i)
				if curr.x == next.x and curr.y == next.y:
					self.vertical_edges.append(i)
		else:
			for i in range(len(self.face.loops)):
				curr = self.get_vertex(i)
				next = self.get_vertex(i + 1)
				if curr.y == next.y:
					self.horizontal_edges.append(i)
				if curr.x == next.x:
					self.vertical_edges.append(i)
		log(DEBUG, "Horizontal edges in face " + str(self.face.index) + " are " + str(self.horizontal_edges), ["init"])
		log(DEBUG, "Vertical edges in face " + str(self.face.index) + " are " + str(self.vertical_edges), ["init"])
	
	def __eq__(self, other):
		if other == None:
			return False
		return self.get_face() == other.get_face()
	
	def __ne__(self, other):
		if other == None:
			return True
		return self.get_face() != other.get_face()
	
	def __str__(self):
		return "XFACE(Face: " + str(self.face.index) + ", Plane: " + self.get_plane_string() + ", Solved: " + str(self.is_solved) + ", Score: " + str(self.get_score()) + ", AlignedHorizontal: " + str(self.horizontal_edges) + ", AlignedVertical: " + str(self.vertical_edges) + ")"
################################################################
################################################################
###########################
## PIXEL UV SOLVER CLASS ##
###########################
# This class is the one that does the work. It heavily relies on the XFace class
# to know the order in which it should solve the faces and other things
class PixelUVSolver:
	
	pixel_2d_size = None
	pixels_per_3d_unit = None
	
	def init(px_2d, px_3d):
		PixelUVSolver.pixel_2d_size = px_2d
		PixelUVSolver.pixels_per_3d_unit = px_3d

	def snap_to_pixel(point):
		for i in range(2):
			prev_pixel_index = int(point[i]//PixelUVSolver.pixel_2d_size)
			next_pixel_index = prev_pixel_index + 1
			
			prev_pixel_pos = prev_pixel_index * PixelUVSolver.pixel_2d_size
			next_pixel_pos = next_pixel_index * PixelUVSolver.pixel_2d_size
			
			if point[i] <= prev_pixel_pos + (PixelUVSolver.pixel_2d_size * 0.6):
				point[i] = prev_pixel_pos
			else:
				point[i] = next_pixel_pos
		return point

	def get_signed_angle(vectora, vectorb):
		normal = vectora.normalized().cross(vectorb.normalized()).normalized()
		return math.atan2(vectora.cross(vectorb).dot(normal), vectora.dot(vectorb))

	def get_length2d(length3d):
		return int(PixelUVSolver.pixels_per_3d_unit * round(length3d - 0.01, 1)) * PixelUVSolver.pixel_2d_size

	def rotate_around(point_to_rotate, point_around, angle_radians):
		ptr = point_to_rotate.copy()
		pa = point_around.copy()
		
		s = math.sin(angle_radians)
		c = math.cos(angle_radians)

		ptr = ptr - pa
		
		xnew = ptr.x * c - ptr.y * s
		ynew = ptr.x * s + ptr.y * c
		
		ptr.x = xnew
		ptr.y = ynew
		
		ptr = ptr + pa

		return ptr

	def solve_position_for(xface, index, combination):
		log(DEBUG, "Solving vertex position for face " + str(xface.get_face().index) + " on index " + str(index) + " and combination " + str(combination), ["pixeluv"])
		vert_to = xface.get_vertex(index)
		
		vert_comb_0 = xface.get_vertex(combination[0])
		vert_comb_1 = xface.get_vertex(combination[1])
		vec_comb = [(vert_comb_1 - vert_comb_0), (vert_comb_0 - vert_comb_1)]
		
		vert_comb_0_uv = xface.get_uv(combination[0])
		vert_comb_1_uv = xface.get_uv(combination[1])
		vec_comb_uv = [(vert_comb_1_uv - vert_comb_0_uv), (vert_comb_0_uv - vert_comb_1_uv)]
		
		solved_positions = []
		for i in range(len(combination)):
			vert_from = xface.get_vertex(combination[i])
			vert_from_uv = xface.get_uv(combination[i])
			length2d = PixelUVSolver.get_length2d((vert_to - vert_from).length)
			vectofrom = vert_to - vert_from
			angle = PixelUVSolver.get_signed_angle(vec_comb[i], vectofrom)
			if i == 1:
				angle = -angle
			log(DEBUG, "The angle for " + str(combination[i]) + " is " + str(math.degrees(angle)), ["pixeluv"])
			
			position_without_rotate = vert_from_uv + (vec_comb_uv[i].normalized() * length2d)
			position_rotated = PixelUVSolver.rotate_around(position_without_rotate, vert_from_uv, angle)
			solved_positions.append(position_rotated)
		
		result = sum(solved_positions, Vector().to_2d()) / len(solved_positions)
		log(DEBUG, "Solved position is: " + str(result), ["pixeluv"])
		return result
	
	def solve_face(xface, force_use_edges = False):
		log(INFO, "Solving UV for face " + str(xface.get_face().index))
		solved_adjacent = []
		
		for linked_xface in xface.get_linked_xfaces():
			log(DEBUG, "Linked xface: " + str(linked_xface))
			if linked_xface.solved() and linked_xface.get_plane() == xface.get_plane():
				solved_adjacent.append(linked_xface)
		solved_adjacent = sorted(solved_adjacent, key=lambda xface: xface.get_score(), reverse=True)
		log(INFO, "Solved adjacent xfaces: ")
		for s in solved_adjacent:
			log(INFO, str(s))
		
		best_adjacent_edge = None
		other_adjacent_edge = None
		other_xface = None
		for adjacent in solved_adjacent:
			((self_aligned, other_aligned)) = xface.find_matching_same_alignment_edges(adjacent)
			if len(self_aligned) > 0 and not force_use_edges:
				best_adjacent_edge = self_aligned[0]
				other_adjacent_edge = other_aligned[0]
				other_xface = adjacent
				log(DEBUG, "Best solved with aligned edges adjacent xface: " + str(other_xface))
				break
		
		if len(solved_adjacent) > 0 and other_xface == None and not force_use_edges:
			adjacent = solved_adjacent[0]
			((self_matching, other_matching)) = xface.find_matching_edges(adjacent)
			best_adjacent_edge = self_matching[0]
			other_adjacent_edge = other_matching[0]
			other_xface = adjacent
			log(DEBUG, "Best solved adjacent xface: " + str(other_xface))
		
		fixed_vertices = set()
		starting_index = 0
		direction = "HORIZONTAL"
		direction_sign = 1
		fix_rotation = False
		if xface.get_plane() == xface.DOWN:
			direction_sign *= -1
		if other_xface != None:
			xface_vert1_index = best_adjacent_edge
			xface_vert2_index = best_adjacent_edge + 1
			xface_vert1 = xface.get_vertex(xface_vert1_index)
			xface_vert2 = xface.get_vertex(xface_vert2_index)
			
			other_vert1_index = other_adjacent_edge
			other_vert2_index = other_adjacent_edge + 1
			other_vert1 = other_xface.get_vertex(other_vert1_index)
			other_vert2 = other_xface.get_vertex(other_vert2_index)
			
			vert1_uv = None
			vert2_uv = None
			if xface_vert1 == other_vert1:
				vert1_uv = other_xface.get_uv(other_vert1_index)
				vert2_uv = other_xface.get_uv(other_vert2_index)
			else:
				vert1_uv = other_xface.get_uv(other_vert2_index)
				vert2_uv = other_xface.get_uv(other_vert1_index)
			xface.update_uv(xface_vert1_index, vert1_uv)	
			xface.update_uv(xface_vert2_index, vert2_uv)
			fixed_vertices.add(xface_vert1_index)
			fixed_vertices.add(xface_vert2_index)
			starting_index = xface_vert2_index + 1
		else:
			if xface.get_score() > 0:
				log(DEBUG, "This face has some aligned edges. Will be adjusted using aligned edges")
				if xface.get_topmost_horizontal_edge() != None:
					starting_index = xface.get_topmost_horizontal_edge()
					direction = "HORIZONTAL"
					direction_sign *= -1
				elif xface.get_botmost_horizontal_edge() != None:
					starting_index = xface.get_botmost_horizontal_edge()
					direction = "HORIZONTAL"
				elif xface.get_rightmost_vertical_edge() != None:
					starting_index = xface.get_rightmost_vertical_edge()
					direction = "VERTICAL"
				elif xface.get_leftmost_vertical_edge() != None:
					starting_index = xface.get_leftmost_vertical_edge()
					direction = "VERTICAL"
					direction_sign *= -1
				else:
					raise Exception("Not possible to have an xface with score greater than 0 and no aligned edges " + str(xface))
			else:
				log(DEBUG, "This face does not have any aligned edges nor solved near faces, rotation will be fixed but won't be perfect!")
				fix_rotation = True
		index = None
		if fix_rotation:
			index = xface.get_topmost_vertex_index()
		else:
			index = starting_index
		log(DEBUG, "Starting solving uv loop for face " + str(xface), ["pixeluv"])
		while len(fixed_vertices) != xface.get_face_length():
			if len(fixed_vertices) == 0:
				log(DEBUG, str(index) + " will be set at 0.0, 0.0", ["pixeluv"])
				xface.update_uv(index, PixelUVSolver.snap_to_pixel(Vector((0.0, 0.0))))
				fixed_vertices.add(index)
			elif len(fixed_vertices) == 1:
				fixed_index = fixed_vertices.pop()
				fixed_vertices.add(fixed_index)
				
				vert_to = xface.get_vertex(index)
				vert_from = xface.get_vertex(fixed_index)
				
				length2d = PixelUVSolver.get_length2d((vert_to - vert_from).length) * direction_sign
				
				position = None
				if fix_rotation:
					fix_rot_dir_vec = xface.get_basis_converted_edge(index - 1).to_2d().normalized()
					position = fix_rot_dir_vec * length2d
				elif direction == "HORIZONTAL":
					position = Vector((length2d, 0.0))
				else:
					position = Vector((0.0, length2d))
					
				log(DEBUG, str(index) + " will be set at " + str(position), ["pixeluv"])
				xface.update_uv(index, PixelUVSolver.snap_to_pixel(position))
				fixed_vertices.add(index)
			else:
				estimated_positions = []
				for combination in list(combinations(fixed_vertices, 2)):
					estimated_positions.append(PixelUVSolver.solve_position_for(xface, index, combination))
				position = sum(estimated_positions, Vector().to_2d()) / len(estimated_positions)
				log(DEBUG, str(index) + " will be set at " + str(position), ["pixeluv"])
				xface.update_uv(index, PixelUVSolver.snap_to_pixel(position))
				fixed_vertices.add(index)
			index += 1
		if fix_rotation:
			log(DEBUG, "Solved face " + str(xface) + "!")
			xface.solve()
			log(INFO, "Fixed rotation on face " + str(xface.get_face().index) + ". It might not be perfect")
		elif xface.is_3d_and_uv_aligned() or force_use_edges:
			xface.solve()
			log(DEBUG, "Solved face " + str(xface) + "!")
			if force_use_edges and not xface.is_3d_and_uv_aligned():
				log(WARN, "Force use edges was activated, but 3d and 2d edges are not aligned!")
		else:
			log(INFO, "Solved face for " + str(xface) + " does not match the alignment between 2d and 3d, re-solving forcing use of aligned edges")
			PixelUVSolver.solve_face(xface, True)
	
	def snap_face_uv_to_pixel(xface, selection_only):
		if not selection_only or xface.get_face().select:
			for index in range(xface.get_face_length()):
				xface.update_uv(index, PixelUVSolver.snap_to_pixel(xface.get_uv(index)))

################################################################

class PixelTexturizerOperator(bpy.types.Operator):
	bl_label = "Pixel Texturizer"
	bl_idname = "rabid.pixel_texturizer"
	
	# Default values
	pixels_per_3d_unit = 10
	pixel_2d_size = 1.0/32.0
	only_selection = True
	
	def pack_together(self, context, selection_only):
		prev_area_type = bpy.context.area.type
		prev_ui_type = bpy.context.area.ui_type
		bpy.context.area.type = 'IMAGE_EDITOR'
		bpy.context.area.ui_type = 'UV'
		obj = context.active_object
		me = obj.data
		bm = bmesh.from_edit_mesh(me)
		uv_layer = bm.loops.layers.uv.verify()
		pivot_ori = bpy.context.space_data.pivot_point
		
		UV_verts = []
		c = 0
		
		for f in bm.faces:
			if not selection_only or f.select:
				for l in f.loops:
					luv = l[uv_layer]
					luv.select = True
					if luv.select and luv.uv not in UV_verts and c != 2:
						UV_verts.append(luv.uv)
						c += 1

		if len(UV_verts) == 2:
			distance = math.sqrt((UV_verts[0].x - UV_verts[1].x)**2 + (UV_verts[0].y - UV_verts[1].y)**2)
			
			bpy.ops.uv.pack_islands(rotate=False, margin=0.05)
			
			distance2 = math.sqrt((UV_verts[0].x - UV_verts[1].x)**2 + (UV_verts[0].y - UV_verts[1].y)**2)
			
			Scale = distance/distance2
			bpy.context.space_data.pivot_point = 'CURSOR'
			bpy.ops.uv.cursor_set(location=(0,0))
			bpy.ops.uv.select_linked()
			bpy.ops.transform.resize(value=(Scale,Scale,Scale), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False)
			bpy.context.space_data.pivot_point = ''+pivot_ori+''
			bpy.context.area.type = prev_area_type
			bpy.context.area.ui_type = prev_ui_type
		else:
			self.report({"ERROR"}, "No island selected")
	
	def run(self, context, pixels_in_3D_unit, texture_size, selection_only):
		self.pixels_per_3d_unit = pixels_in_3D_unit
		self.pixel_2d_size = 1.0/float(texture_size)
		self.only_selection = selection_only
		
		# --- ACTIVE OBJECT DATA --- #
		obj = context.active_object
		me = obj.data
		bm = bmesh.from_edit_mesh(me)
		uv_layer = bm.loops.layers.uv.verify()
		XFace.init(uv_layer)

		# --- CHECKS --- #
		vertices = set()
		for vert in bm.verts:
			if vert.co.copy().freeze() in vertices:
				log(ERROR, "The vert " + str(vert.co.copy.freeze()) + " is already in the set")
			vertices.add(vert.co.copy().freeze())

		if len(bm.verts) != len(vertices):
			raise Exception("There are duplicated vertices! Cannot proceed")
		
		# --- BUILD XFACES --- #
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

		lateral_xfaces = sorted(lateral_xfaces, key=lambda xface: xface.get_score(), reverse=True)
		top_xfaces = sorted(top_xfaces, key=lambda xface: xface.get_score(), reverse=True)
		down_xfaces = sorted(down_xfaces, key=lambda xface: xface.get_score(), reverse=True)

		# --- SOLVE XFACES --- #
		PixelUVSolver.init(self.pixel_2d_size, self.pixels_per_3d_unit)
		xfaces_lists = [lateral_xfaces, top_xfaces, down_xfaces]
		solved_faces = set()
		uv_islands = []
		for xface_list in xfaces_lists:
			for xface in xface_list:
				if not xface.get_face() in solved_faces:
					new_uv_island = []
					processing_xfaces = [xface]
					while len(processing_xfaces) > 0:
						current_xface = processing_xfaces.pop(0)
						PixelUVSolver.solve_face(current_xface)
						solved_faces.add(current_xface.get_face())
						new_uv_island.append(current_xface.get_face())
						linked_xfaces = current_xface.get_linked_xfaces()
						for linked_xface in linked_xfaces:
							if not self.only_selection or linked_xface.get_face().select:
								if not (linked_xface.get_face() in solved_faces or linked_xface in processing_xfaces):
									if linked_xface.get_plane() == xface.get_plane():
										processing_xfaces.append(linked_xface)
						processing_xfaces = sorted(processing_xfaces, key=lambda xface: xface.get_score(), reverse=True)
						log(DEBUG, "After solving, these are the processing xfaces")
						for p in processing_xfaces:
							log(DEBUG, str(p))
					uv_islands.append(new_uv_island)

		self.pack_together(context, selection_only)
		for xface in lateral_xfaces + top_xfaces + down_xfaces:
			PixelUVSolver.snap_face_uv_to_pixel(xface, selection_only)
		bmesh.update_edit_mesh(me)

		log(INFO, "Lateral faces: " + str(len(lateral_xfaces)))
		for xface in lateral_xfaces:
			log(INFO, xface)
		log(INFO, "Top faces: " + str(len(top_xfaces)))
		for xface in top_xfaces:
			log(INFO, xface)
		log(INFO, "Down faces: " + str(len(down_xfaces)))
		for xface in down_xfaces:
			log(INFO, xface)
	
	def execute(self, context):
		layout = self.layout
		scene = context.scene
		pixel_texturizer = scene.pixel_texturizer
		try:	
			self.run(context, pixel_texturizer.pixels_in_3D_unit, pixel_texturizer.texture_size, pixel_texturizer.selection_only)
			self.report({'INFO'}, "All ok!")
		except Exception as exception:
			self.report({'ERROR'}, str(exception))
		return {'FINISHED'}

## REGISTRATION STUFF ##
classes = [PixelTexturizerProperties, PixelTexturizerMainPanel, PixelTexturizerOperator]

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
		
	bpy.types.Scene.pixel_texturizer = bpy.props.PointerProperty(type = PixelTexturizerProperties)
 
def unregister():
	for cls in classes:
		bpy.utils.unregister_class(cls)
 
	del bpy.types.Scene.pixel_texturizer

if __name__ == "__main__":
	register()