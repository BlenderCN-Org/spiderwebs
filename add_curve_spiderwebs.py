# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


# Import modules.
if "bpy" in locals():
    import importlib
    if "mesh_tools" in locals():
        importlib.reload(mesh_tools)
    if "curve_tools" in locals():
        importlib.reload(curve_tools)
else:
    from . import mesh_tools
    from . import curve_tools

import itertools
import random
import bpy
from bpy.props import (IntProperty,
                       FloatProperty,
                       BoolProperty,
                       EnumProperty)


class Spiderweb(bpy.types.Operator):
    """Add a spiderweb (or wires) between the selected objects"""
    bl_idname = "curve.spiderweb"
    bl_label = "Create spiderweb"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    def __init__(self):
        # Because creating a lot of wires can take some time and slow down the
        # viewport, set the initial amount of wires to 50 if it is higher.
        if self.amount > 50:
            self.amount = 50

    amount = IntProperty(name="Amount",
                         description="The number of wires to create",
                         default=20,
                         min=2,
                         max=999999,
                         soft_max=100)
    main_iterations = IntProperty(name="Iterations",
                                  description="Iterations",
                                  default=1,
                                  min=1,
                                  max=100)
    include_ends = BoolProperty(name="Include ends",
                                description="Include ends",
                                default=True)
    sub_iterations = IntProperty(name="Iterations",
                                 description="Iterations",
                                 default=3,
                                 min=0,
                                 max=999999,
                                 soft_max=100)
    method_items = [('PIVOT', 'Pivot', 'Sample from pivot points (Will not '
                                       'return more points then the number '
                                       'of selected objects'),
                    ('VOLUME', 'Volume', 'Sample from the volume(s)'),
                    ('SURFACE', 'Surface', 'Sample from surface(s)'),
                    ('EDGES', 'Edges', 'Sample from edges'),
                    ('VERTS', 'Vertices', 'Sample from vertices')]
    method = EnumProperty(name="Method",
                          description="Where to sample the end points of the "
                                      "curves from",
                          items=method_items,
                          default='SURFACE')
    seed = IntProperty(name="Seed",
                       description="The seed to use for the generation "
                                   "(change it to get a different variant "
                                   "of the web)",
                       default=0)
    drape_min = FloatProperty(name="Drape min",
                              description="The minimum drape of the strands",
                              default=-1.0,
                              soft_min=-50.0,
                              soft_max=50.0,
                              step=10)
    drape_max = FloatProperty(name="Drape max",
                              description="The maximum drape of the strands",
                              default=0,
                              soft_min=-50.0,
                              soft_max=50.0,
                              step=10)
    length_solver = BoolProperty(name="Length solver",
                                 description="Length solver",
                                 default=True)

    # Draw
    def draw(self, context):
        random.seed(self.seed)
        layout = self.layout

        # Options
        box = layout.box()
        box.label(text="Main strands")
        box.prop(self, 'amount')
        box.prop(self, 'main_iterations')
        box = layout.box()
        box.label(text="Sub strands")
        box.prop(self, 'include_ends')
        box.prop(self, 'sub_iterations')
        box = layout.box()
        box.label(text="General options")
        box.prop(self, 'method')
        box.prop(self, 'seed')
        box.prop(self, 'drape_min')
        box.prop(self, 'drape_max')
        box.prop(self, 'length_solver')

    # Poll
    @classmethod
    def poll(cls, context):
        if context.selected_objects:
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    return True

    # Execute
    def execute(self, context):

        def drape(splines):
            random.seed(self.seed)
            for i, spline in enumerate(splines):
                # random.seed(self.seed + i)
                # For now only a spline with 3 points works
                spline[1].z += random.uniform(self.drape_min, self.drape_max)

            return splines

        selected_objects = bpy.context.selected_objects
        web_objects = [obj for obj in selected_objects if obj.type == 'MESH']

        # Get (random) points on/in the selected objects.
        end_points = {}
        # Determine how many points to create per object,
        # to get <amount> total points.
        quotient, remainder = divmod(self.amount, len(web_objects))
        # Randomize order of selected objects
        random.seed(self.seed)
        random.shuffle(web_objects)
        for i, obj in enumerate(web_objects):
            if i in range(remainder):
                obj_amount = quotient + 1
            else:
                obj_amount = quotient
            points = mesh_tools.get_points(obj,
                                           amount=obj_amount,
                                           method=self.method,
                                           apply_modifiers=True,
                                           seed=self.seed)
            end_points[obj] = points

        # Create splines between two random points.
        if not sum(len(v) for v in end_points.values()) > 1:
            # We need at least 2 points.
            return

        # Create the points of the main strands (every spline has 3 points)
        main_splines = []
        end_vectors = list(itertools.chain(*end_points.values()))
        random.seed(self.seed)
        for i in range(self.main_iterations):
            for ip, start_point in enumerate(end_vectors):
                for _ in range(9999):
                    end_point = random.choice(end_vectors)
                    if not end_point == start_point:
                        break
                mid_point = start_point + (end_point - start_point) * 0.5
                main_splines.append((start_point, mid_point, end_point))

        # Drape main splines
        # main_splines = drape(main_splines)

        # Create the points of the sub strands (every spline has 3 points)
        sub_splines = []
        resolution_points = [curve_tools.get_nurbs_points(spline)
                             for spline in main_splines]
        random.seed(self.seed)
        for i in range(self.sub_iterations):
            for _ in range(0, len(resolution_points), 2):
                # Pick a random spline to start from
                spline1 = random.choice(resolution_points)
                # Pick a random spline to end which is not the start spline
                for _ in range(9999):
                    spline2 = random.choice(resolution_points)
                    if not spline2 == spline1:
                        break
                # Pick a random start point from spline1
                start_index = int(random.triangular(0, len(spline1)))
                start_point = spline1[start_index]
                # Pick a random end point from spline2
                end_index = int(random.triangular(0, len(spline2)))
                end_point = spline2[end_index]
                # Create the mid point
                mid_point = start_point + (end_point - start_point) * 0.5
                # Add the points to sub_splines
                sub_splines.append((start_point, mid_point, end_point))

        # Drape the sub splines
        # sub_splines = drape(sub_splines)

        curve = curve_tools.create_curve(name="web")
        for spline in main_splines + sub_splines:
            points = [p for p in spline]
            curve_tools.create_spline(curve=curve, points=points)

        web = bpy.data.objects.new("web", curve)
        bpy.context.scene.objects.link(web)
        bpy.context.scene.objects.active = web


        # curve = curve_tools.create_curve(name="web")
        # for i in range(self.main_iterations):
        #     end_vectors = list(itertools.chain(*end_points.values()))
        #     for ip, p in enumerate(end_vectors):
        #         for _ in range(9999):
        #             p2 = random.choice(end_vectors)
        #             if not p2 == p:
        #                 break
        #         # points = end_vectors[:]
        #         # points.pop(ip)
        #         # p2 = random.choice(points)
        #         curve, spline = curve_tools.create_spline(curve=curve,
        #                                                   points=[p, p2])

        # web = bpy.data.objects.new("web", curve)
        # bpy.context.scene.objects.link(web)
        # bpy.context.scene.objects.active = web

        # end_positions = []
        # scene = context.scene

        # # Step 3: Create "Main strands" using particles for end positions
        # if not len(end_positions) > 1:
        #     return
        # curve = bpy.data.curves.new("cobweb", 'CURVE')
        # curve.dimensions = '3D'
        # curve.fill_mode = 'FULL'
        # for i in range(self.main_iterations):
        #     for ip, loc in enumerate(end_positions):
        #         points = end_positions[:]
        #         points.pop(ip)
        #         spline = curve.splines.new('NURBS')
        #         spline.points.add(count=2)
        #         loc1 = loc
        #         random.seed(self.seed + i * ip * 100)
        #         loc3 = random.choice(points)
        #         loc2 = loc + ((loc3 - loc) * .5)
        #         spline.points[0].co = loc1.to_4d()
        #         spline.points[1].co = loc2.to_4d()
        #         spline.points[2].co = loc3.to_4d()
        #         spline.use_endpoint_u = True
        #         spline.order_u = 3

        # self.drape_web(curve)

        # #Step 4: Create "Sub strands"
        # if self.include_ends:
        #     divide = 3.8
        # else:
        #     divide = 4
        # curve_copy = curve.copy()
        # for i in range(self.sub_iterations):
        #     mid_points = self.get_mid_points(curve_copy, divide, i)
        #     for ip, loc in enumerate(mid_points):
        #         points = mid_points[:]
        #         points.pop(ip)
        #         spline = curve.splines.new('NURBS')
        #         spline.points.add(count=2)
        #         loc1 = loc.to_3d()
        #         random.seed(self.seed + i * ip * 133)
        #         loc3 = random.choice(points).to_3d()
        #         loc2 = loc + ((loc3 - loc) * .5)
        #         spline.points[0].co = loc1.to_4d()
        #         spline.points[1].co = loc2.to_4d()
        #         spline.points[2].co = loc3.to_4d()
        #         spline.use_endpoint_u = True
        #         spline.order_u = 3

        #         # !!!TEMP DRAPE
        #         random.seed(self.seed + i * ip * 100)
        #         drape = random.uniform(self.drape_min, self.drape_max)
        #         length = self.spline_length(spline)
        #         average_length = self.average_spline_length(curve)
        #         if self.length_solver:
        #             drape = length * drape / average_length
        #         spline.points[1].co.z += drape

        # cobweb = bpy.data.objects.new("cobweb", curve)
        # bpy.context.scene.objects.link(cobweb)
        # # Delete the object with the particle system, we don't need it anymore.
        # scene.objects.unlink(particle_object)
        # bpy.data.objects.remove(particle_object)
        # # Add some drape to the splines.
        # # Select the cobweb and make it the active object.
        # cobweb.select = True
        # bpy.context.scene.objects.active = cobweb

        return {'FINISHED'}

    # Invoke
    def invoke(self, context, event):
        self.execute(context)

        return {'FINISHED'}
