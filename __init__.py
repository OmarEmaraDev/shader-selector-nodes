"""
Copyright (C) 2021 Omar Emara
mail@OmarEmara.dev

Created by Omar Emara

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


bl_info = {
    "name":        "Shader Selector Nodes",
    "description": "Shader nodes that allow selection of images and textures.",
    "author":      "Omar Emara",
    "version":     (1, 0, 0),
    "blender":     (2, 93, 0),
    "location":    "Shader Nodes -> Add Menu -> Add Texture -> Image Selector",
    "category":    "Node",
    "warning":     "This version is still in development."
}

import bpy
from bpy.props import *

def updateNodeTree(self, context):
    node = context.active_node.id_data.nodes[self.nodeName]
    node.updateNodeTree()

class ImageListItem(bpy.types.PropertyGroup):
    bl_idname = "SSN_ImageListItem"

    image: PointerProperty(type = bpy.types.Image, update = updateNodeTree)
    nodeName: StringProperty()

class ImageUIList(bpy.types.UIList):
    bl_idname = "SSN_UL_ImageUIList"

    def draw_item(self, context, layout, itemContainer, item, icon, activeContainer,
                  activePropertyName, index):
        row = layout.row(align = True)
        row.template_ID(item, "image", new = "image.new", open = "image.open")
        activeIndex = getattr(activeContainer, activePropertyName)
        row.label(icon = "LAYER_ACTIVE" if index == activeIndex else "LAYER_USED")

class BaseOperator(bpy.types.Operator):
    nodeName: StringProperty()

    def getNode(self, context):
        return context.active_node.id_data.nodes[self.nodeName]

class AddImage(BaseOperator):
    bl_idname = "ssn.add_image"
    bl_label = "Add"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        node = self.getNode(context)
        item = node.imageItems.add()
        item.nodeName = self.nodeName
        node.updateNodeTree()
        return{'FINISHED'}

class BrowseImages(BaseOperator):
    bl_idname = "ssn.browse_images"
    bl_label = "Browse"
    bl_options = {'REGISTER', 'UNDO'}
    
    filter_image: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_folder: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype = "DIR_PATH")
    files: CollectionProperty(type = bpy.types.OperatorFileListElement,
                              options = {'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, _event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        node = self.getNode(context)
        imageItems = node.imageItems
        for imageFile in self.files:
            image = bpy.data.images.load(self.directory + imageFile.name,  check_existing = True)
            item = imageItems.add()
            item.image = image
            item.nodeName = self.nodeName
        node.updateNodeTree()
        return{'FINISHED'}

class ClearImages(BaseOperator):
    bl_idname = "ssn.clear_images"
    bl_label = "Clear"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        node = self.getNode(context)
        node.imageItems.clear()
        node.updateNodeTree()
        return{'FINISHED'}

class RemoveImage(BaseOperator):
    bl_idname = "ssn.remove_image"
    bl_label = "Remove"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        node = self.getNode(context)
        node.imageItems.remove(node.activeImageIndex)
        if node.activeImageIndex == len(node.imageItems) and node.activeImageIndex != 0:
            node.activeImageIndex -= 1
        node.updateNodeTree()
        return{'FINISHED'}

selectionTypeItems = [
    ("INDEX", "Index", "", "NONE", 0),
    ("RANDOM_PER_OBJECT", "Random Per Object", "", "NONE", 1),
    ("RANDOM_PER_ISLAND", "Random Per Island", "", "NONE", 2),
]

class ImageSelectorShaderNode(bpy.types.ShaderNodeCustomGroup):
    bl_idname = "SSN_ImageSelectorShaderNode"
    bl_label = "Image Selector"
    bl_width_default = 240

    activeImageIndex: IntProperty()
    imageItems: CollectionProperty(type = ImageListItem)

    selectionType: EnumProperty(name = "Selection Type", items = selectionTypeItems,
                                update = lambda self, context : self.updateNodeTree())

    def draw_buttons(self, context, layout):
        layout.prop(self, "selectionType", text = "")
        layout.template_list(ImageUIList.bl_idname, "", self, "imageItems", self, "activeImageIndex")
        col = layout.column(align = True)
        row = col.row(align = True)
        properties = row.operator(AddImage.bl_idname)
        properties.nodeName = self.name
        properties = row.operator(BrowseImages.bl_idname)
        properties.nodeName = self.name
        row = col.row(align = True)
        properties = row.operator(RemoveImage.bl_idname)
        properties.nodeName = self.name
        properties = row.operator(ClearImages.bl_idname)
        properties.nodeName = self.name

    def init(self, context):
        self.node_tree = bpy.data.node_groups.new(f"{self.name}_internal_node_tree", "ShaderNodeTree")
        self.updateNodeTree()

    def free(self):
        if self.node_tree.users == 1:
            bpy.data.node_groups.remove(self.node_tree, do_unlink = True)

    def updateNodeTree(self):
        self.clearNodeTree()
        self.addInputs()
        self.addOutputs()
        self.addNodes()

    def addOutputs(self):
        self.node_tree.outputs.new("NodeSocketColor", "Color")

    def addInputs(self):
        self.node_tree.inputs.new("NodeSocketVector", "Vector")
        if self.selectionType == "INDEX":
            self.node_tree.inputs.new("NodeSocketInt", "Index")

    def addNodes(self):
        nodes = self.node_tree.nodes
        links = self.node_tree.links

        inputNode = nodes.new("NodeGroupInput")
        outputNode = nodes.new("NodeGroupOutput")

        inputs = inputNode.outputs
        outputs = outputNode.inputs

        if len(self.imageItems) == 0:
            return

        vectorIsLinked = self.inputs["Vector"].is_linked

        if len(self.imageItems) == 1:
            imageNode = nodes.new("ShaderNodeTexImage")
            imageNode.image = self.imageItems[0].image
            if vectorIsLinked:
                links.new(imageNode.inputs["Vector"], inputs["Vector"])
            links.new(outputs["Color"], imageNode.outputs["Color"])
            return

        if self.selectionType == "INDEX":
            indexSocket = inputs["Index"]
        else:
            if self.selectionType == "RANDOM_PER_OBJECT":
                objectInfoNode = nodes.new("ShaderNodeObjectInfo")
                randomSocket = objectInfoNode.outputs["Random"]
            if self.selectionType == "RANDOM_PER_ISLAND":
                geometryNode = nodes.new("ShaderNodeNewGeometry")
                randomSocket = geometryNode.outputs["Random Per Island"]

            multiplyNode = nodes.new("ShaderNodeMath")
            multiplyNode.operation = "MULTIPLY"
            links.new(multiplyNode.inputs[0], randomSocket)
            multiplyNode.inputs[1].default_value = len(self.imageItems)
            indexSocket = multiplyNode.outputs["Value"]

        floorNode = nodes.new("ShaderNodeMath")
        floorNode.operation = "FLOOR"
        links.new(floorNode.inputs["Value"], indexSocket)

        multiplyNodes = []
        for i, imageItem in enumerate(self.imageItems):
            imageNode = nodes.new("ShaderNodeTexImage")
            imageNode.image = imageItem.image
            if vectorIsLinked:
                links.new(imageNode.inputs["Vector"], inputs["Vector"])

            compareNode = nodes.new("ShaderNodeMath")
            compareNode.operation = "COMPARE"
            links.new(compareNode.inputs[0], floorNode.outputs["Value"])
            compareNode.inputs[1].default_value = i

            multiplyNode = nodes.new("ShaderNodeMixRGB")
            multiplyNode.blend_type = "MULTIPLY"
            multiplyNode.inputs["Fac"].default_value = 1
            links.new(multiplyNode.inputs["Color1"], imageNode.outputs["Color"])
            links.new(multiplyNode.inputs["Color2"], compareNode.outputs["Value"])
            multiplyNodes.append(multiplyNode)

        lastNode = multiplyNodes[0]
        for i in range(1, len(multiplyNodes)):
            addNode = nodes.new("ShaderNodeMixRGB")
            addNode.blend_type = "ADD"
            addNode.inputs["Fac"].default_value = 1
            links.new(addNode.inputs["Color1"], lastNode.outputs["Color"])
            links.new(addNode.inputs["Color2"], multiplyNodes[i].outputs["Color"])
            lastNode = addNode

        links.new(outputNode.inputs["Color"], lastNode.outputs["Color"])

    def clearNodeTree(self):
        self.node_tree.inputs.clear()
        self.node_tree.outputs.clear()
        self.node_tree.links.clear()
        self.node_tree.nodes.clear()

def drawMenu(self, context):
    self.layout.separator()
    operator = self.layout.operator("node.add_node", text = "Image Selector")
    operator.type = ImageSelectorShaderNode.bl_idname
    operator.use_transform = True
 
def register():
    bpy.utils.register_class(ImageListItem)
    bpy.utils.register_class(ImageUIList)
    bpy.utils.register_class(AddImage)
    bpy.utils.register_class(BrowseImages)
    bpy.utils.register_class(ClearImages)
    bpy.utils.register_class(RemoveImage)
    bpy.utils.register_class(ImageSelectorShaderNode)
    bpy.types.NODE_MT_category_SH_NEW_TEXTURE.append(drawMenu)
 
def unregister():
    bpy.utils.unregister_class(ImageListItem)
    bpy.utils.unregister_class(ImageUIList)
    bpy.utils.unregister_class(AddImage)
    bpy.utils.unregister_class(BrowseImages)
    bpy.utils.unregister_class(ClearImages)
    bpy.utils.unregister_class(RemoveImage)
    bpy.utils.unregister_class(ImageSelectorShaderNode)
    bpy.types.NODE_MT_category_SH_NEW_TEXTURE.remove(drawMenu)

if __name__ == "__main__":
    register()
