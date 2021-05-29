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
from .pixeroperator import PixerOperator

bl_info = {
    "name": "Pixer",
    "author": "Rabid",
    "version": (0, 95),
    "blender": (2, 92, 0),
    "description": "Adjusts the UVs from a model to set the textures to pixels",
    "wiki_url": "https://github.com/RabidTunes/pixeltexturizer",
    "category": "UV"
}


class PixerProperties(bpy.types.PropertyGroup):
    pixels_in_3D_unit: bpy.props.IntProperty(name="Pixels/unit",
                                             description="How many squares are inside a 3D unit (you can use "
                                                         "ortographic view to check this)",
                                             default=10, min=1)
    texture_size: bpy.props.IntProperty(name="Texture Size", description="Size of texture. Assumes it is squared",
                                        default=32, min=1)
    selection_only: bpy.props.BoolProperty(name="Selection only",
                                           description="Check this if you want to apply the texturizer only to "
                                                       "selected faces",
                                           default=False)


class PixerMainPanel(bpy.types.Panel):
    bl_label = "Pixer"
    bl_idname = "Pixer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Pixer"

    def draw(self, context: bpy.context):
        layout = self.layout
        scene = context.scene
        pixer = scene.pixer

        layout.prop(pixer, "pixels_in_3D_unit")
        layout.prop(pixer, "texture_size")
        layout.prop(pixer, "selection_only")

        row = layout.row()
        row.label(icon='WORLD_DATA')
        row.operator(text="Pixelize!", operator="rabid.pixer")
        row.label(icon='WORLD_DATA')


classes = [PixerProperties, PixerMainPanel, PixerOperator]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.pixer = bpy.props.PointerProperty(type=PixerProperties)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.pixer


if __name__ == "__main__":
    register()
