# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
from .pixeltexoperator import PixelTexturizerOperator

bl_info = {
    "name": "PIXX",
    "author": "Rabid",
    "version": (0, 9),
    "blender": (2, 92, 0),
    "description": "Adjusts the UVs from a model to set the textures to pixels",
    "wiki_url": "https://github.com/RabidTunes/pixeltexturizer",
    "category": "UV"
}


class PixelTexturizerProperties(bpy.types.PropertyGroup):
    pixels_in_3D_unit: bpy.props.IntProperty(name="PIXONGOS per 3D unit",
                                             description="How many squares are inside a 3D unit (you can use "
                                                         "ortographic view to check this)",
                                             default=10, min=1)
    texture_size: bpy.props.IntProperty(name="Texture Size", description="Size of texture. Assumes it is squared",
                                        default=32, min=1)
    selection_only: bpy.props.BoolProperty(name="Selection only",
                                           description="Check this if you want to apply the texturizer only to "
                                                       "selected faces",
                                           default=False)


class PixelTexturizerMainPanel(bpy.types.Panel):
    bl_label = "PIXX"
    bl_idname = "PIXX"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PIXX"

    def draw(self, context: bpy.context):
        layout = self.layout
        scene = context.scene
        pixel_texturizer = scene.pixel_texturizer

        layout.prop(pixel_texturizer, "pixels_in_3D_unit")
        layout.prop(pixel_texturizer, "texture_size")
        layout.prop(pixel_texturizer, "selection_only")

        row = layout.row()
        row.label(icon='WORLD_DATA')
        row.operator(text="Pixelize!", operator="rabid.pixel_texturizer")
        row.label(icon='WORLD_DATA')


classes = [PixelTexturizerProperties, PixelTexturizerMainPanel, PixelTexturizerOperator]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.pixel_texturizer = bpy.props.PointerProperty(type=PixelTexturizerProperties)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.pixel_texturizer


if __name__ == "__main__":
    register()
