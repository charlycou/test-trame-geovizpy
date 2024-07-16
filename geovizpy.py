#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoVizPy: Geophysical data visualization with PyVista and Trame
Author: Sylvain Pasquet
v07-2024
"""

# -----------------------------------------------------------------------------
# Import
# -----------------------------------------------------------------------------
import os
import pyvista as pv
from pyvista.trame.ui import plotter_ui

from trame.app import get_server
from trame.ui.vuetify import SinglePageWithDrawerLayout
from trame.widgets import trame
from trame.widgets import vuetify as vuetify
import vtk

import numpy as np
from scipy.interpolate import NearestNDInterpolator
import rasterio
import gemgis as gg

from vtkmodules.util.numpy_support import vtk_to_numpy

from vtkmodules.vtkRenderingCore import (
    vtkRenderer,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
)

# -----------------------------------------------------------------------------
# VTK pipeline
# -----------------------------------------------------------------------------
renderer = vtkRenderer()
renderWindow = vtkRenderWindow()
renderWindow.AddRenderer(renderer)

renderWindowInteractor = vtkRenderWindowInteractor()
renderWindowInteractor.SetRenderWindow(renderWindow)
renderWindowInteractor.GetInteractorStyle().SetCurrentStyleToTrackballCamera()

# -----------------------------------------------------------------------------
# Trame initialization
# -----------------------------------------------------------------------------
pv.OFF_SCREEN = True

server = get_server()
server.client_type = "vue2"
state, ctrl = server.state, server.controller

ctrl.on_server_ready.add(ctrl.view_update)

# -----------------------------------------------------------------------------
# Init Parameters
# -----------------------------------------------------------------------------
seismic_cm = 'plasma'
resistivity_cm = 'viridis'
elevation_cm = 'gist_earth'
z_shift = 0
font_size = 12
nom_page = 'Lautaret'
filepath = 'Lautaret'
bounds = [966860, 6446505, 967275, 6446800] # Aravo
crs = 'EPSG:2154' # Lambert 93

# -----------------------------------------------------------------------------
# Scalar bar arguments
# -----------------------------------------------------------------------------
sargs_dem = dict(fmt="%.0f", color='black',height=0.25, interactive = False,
                 vertical=True, position_x=0.05, position_y=0.7)
sargs_cmd = dict(fmt="%.0f", color='black',height=0.25, interactive = False,
                 vertical=True, position_x=0.9, position_y=0.7)
sargs_seismic = dict(fmt="%.0f", color='black',height=0.25, interactive = False,
                     vertical=True, position_x=0.05, position_y=0.05)
sargs_resistivity = dict(fmt="%.0f", color='black',height=0.25, interactive = False,
                         vertical=True, position_x=0.9, position_y=0.05)
# sargs_mesh = dict(fmt="%.2f", color='black', interactive = True)

# -----------------------------------------------------------------------------
# List vtk files
# -----------------------------------------------------------------------------
vtk_file_list = []

# Seismic vtk files path
vtk_file_list.append('vtk/aravo_seismic_A_topo_ok_time_ok_utm.vtk')
vtk_file_list.append('vtk/aravo_seismic_B_topo_ok_time_ok_utm.vtk')
vtk_file_list.append('vtk/aravo_seismic_C_topo_ok_time_ok_utm.vtk')
vtk_file_list.append('vtk/aravo_seismic_D_topo_ok_time_ok_utm.vtk')
vtk_file_list.append('vtk/aravo_seismic_E_topo_ok_time_ok_utm.vtk')

# ERT vtk files path
# vtk_file_list.append('vtk/aravo_ert_A_nogapfiller_model001_shift.vtk')
# vtk_file_list.append('vtk/aravo_ert_B_nogapfiller_model001_shift.vtk')
# vtk_file_list.append('vtk/aravo_ert_C_nogapfiller_model001_shift.vtk')
# vtk_file_list.append('vtk/aravo_ert_D_nogapfiller_model001_shift.vtk')

# -----------------------------------------------------------------------------
# List tiff files
# -----------------------------------------------------------------------------
tif_file_list = []

# tif files path
tif_file_list.append('tif/mnt_ign_rge_aravo.tif')
tif_file_list.append('tif/cmd_aravo.tif')

# -----------------------------------------------------------------------------
# List of mesh names
# -----------------------------------------------------------------------------
state.name_mesh = []
for k in range(len(vtk_file_list)):
    temp = vtk_file_list[k]
    (dirName, fileName) = os.path.split(temp)
    (filename, fileExtension) = os.path.splitext(fileName)
    state.name_mesh.append(filename[0:15])
    
# -----------------------------------------------------------------------------
# Read mesh profiles with PyVista
# -----------------------------------------------------------------------------
mesh = pv.read(vtk_file_list)

# -----------------------------------------------------------------------------
# Get aerial photography from IGN WMS
# -----------------------------------------------------------------------------
url = 'https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap'
layer='ORTHOIMAGERY.ORTHOPHOTOS'
wms_aerial_array = gg.web.load_as_array(url=url, layer=layer, style='normal', crs=crs, 
                             bbox=[bounds[0],bounds[2], bounds[1], bounds[3]], 
                             size=[600, 600], filetype='image/png',
                             save_image=False)

# -----------------------------------------------------------------------------
# Create mesh from MNT
# -----------------------------------------------------------------------------
# Read DEM raster
mesh_dem = gg.visualization.read_raster(path=tif_file_list[0],
                               nodata_val=9999.0,
                               name='Elevation [m]')
# Warp mesh by elevation
mesh_dem = mesh_dem.warp_by_scalar(scalars="Elevation [m]", factor=1)

# Convert aerial image in mesh+texture
wms_aerial_rgb = gg.visualization.convert_to_rgb(array=wms_aerial_array)
dem = rasterio.open(tif_file_list[0])
mesh_aerial, texture = gg.visualization.drape_array_over_dem(array=wms_aerial_rgb, 
                                                            dem=dem, 
                                                            zmax=3000)
# Translate aerial image mesh (if needed)
mesh_aerial = mesh_aerial.translate([0,0,z_shift],inplace=True)

# -----------------------------------------------------------------------------
# Create mesh from CMD
# -----------------------------------------------------------------------------
# Read CMD raster
mesh_cmd_raw = gg.visualization.read_raster(path=tif_file_list[1],
                               nodata_val=9999.0, name='Resistivity')

# Interpolate CMD data at DEM data
# Get CMD data points
cmd_points = mesh_cmd_raw.GetPoints()
xy_cmd = vtk_to_numpy(cmd_points.GetData())
xy_list = list(zip(xy_cmd[:,0],xy_cmd[:,1]))
array_cmd = mesh_cmd_raw['Resistivity']

# Get points from DEM data
dem_points = mesh_dem.GetPoints()
xy_dem = vtk_to_numpy(dem_points.GetData())

# Interpolation
interp = NearestNDInterpolator(xy_list, array_cmd)
cmd_interp = interp(xy_dem[:,0], xy_dem[:,1])

# Add interpolated resistivity from CMD in DEM mesh
mesh_dem.point_data.set_array(cmd_interp,'Resistivity')
# Translate aerial image mesh (for better display)
mesh_cmd = mesh_dem.translate([0,0,z_shift+0.25])

# ----------------------------------------------------------------------------- 
# List actors and state of visibility
# -----------------------------------------------------------------------------
actor_profile = []
actor_dem = []
actor_cmd = []
state.visibilityList =[True, True, True, True, True]
state.visibilityDEM= [True]
state.visibilityCMD= [True]

# -----------------------------------------------------------------------------
# Get data range
# -----------------------------------------------------------------------------
vel_range = mesh.get_data_range('Velocity')
res_range = mesh_dem.get_data_range('Resistivity')

#-----------------------------------------------------------------------------
# Plotting init
# -----------------------------------------------------------------------------
pl = pv.Plotter(window_size=(800, 600))
pl.set_background('lightgrey')

# Axis box
_ = pl.show_bounds(
    grid='front',
    location='outer',
    all_edges=True,
    # fmt='%1.0f',
    xtitle="X (m)",
    ytitle="Y (m)",
    ztitle="Elevation (m)",
    font_size=font_size,
    fmt='%3i'
    )
cube_axes_actor = pv.CubeAxesActor(pl.camera)

state.setdefault("active_ui", None)

# Show/hide checkbox
class SetVisibilityCallback:
    """Helper callback to keep a reference to the actor being modified."""

    def __init__(self, actor):
        self.actor = actor

    def __call__(self, state):
        self.actor.SetVisibility(state)

# Functions show/hide        
def hide_profile(num,flag):
    actor_profile[num].SetVisibility(flag)
    ctrl.view_update()

def hide_DEM(flag):
    actor_dem[0].SetVisibility(flag)
    ctrl.view_update()
    
def hide_CMD(flag):
    actor_cmd[0].SetVisibility(flag)
    ctrl.view_update()

# Update visibility
def update_profile_visibility(index, visibility):
    state.visibilityList[index] = visibility
    state.dirty("visibilityList")
    hide_profile(index,visibility)

def update_DEM_visibility(visibility):
    state.visibilityDEM[0] = visibility
    state.dirty("visibilityDEM")
    hide_DEM(visibility)

def update_CMD_visibility(visibility):
    state.visibilityCMD[0] = visibility
    state.dirty("visibilityCMD")
    hide_CMD(visibility)
    
# Selection Change
def actives_change(ids):
    _id = ids[0]
    if _id == "1":  # Mesh
        state.active_ui = "Geophysical profiles"
    elif _id == "2":  # topo
        state.active_ui = "Images and maps"
    elif _id == "3":  # scales
        state.active_ui = "Settings"
    else:
        state.active_ui = "nothing"

def ui_card(title, ui_name):
    with vuetify.VCard(v_show=f"active_ui == '{ui_name}'"):
        vuetify.VCardTitle(
            title,
            classes="grey lighten-1 py-1 grey--text text--darken-3",
            style="user-select: none; cursor: pointer",
            hide_details=True,
            dense=True,
        )
        content = vuetify.VCardText(classes="py-2")
    return content
    
def mesh_card():
    with ui_card(title="Geophysical profiles", ui_name="Geophysical profiles"):
        vuetify.VSpacer()
                   
        with vuetify.VCol():
            vuetify.VCheckbox(
                v_for="v, i in visibilityList",
                key="i",
                label=("name_mesh[i]",),
                v_model=("visibilityList[i]",),
                change=(update_profile_visibility, "[i, $event]"),
            )
                
def maps_card():
    with ui_card(title="Images and maps", ui_name="Images and maps"):
        vuetify.VSpacer()
                   
        with vuetify.VCol():     
            vuetify.VCheckbox(
                key="0",
                label="Satellite image",
                v_model=("visibilityDEM[0]",),
                change=(update_DEM_visibility, "[$event]"),
            )
            vuetify.VSpacer()
            vuetify.VSlider(
                # Opacity
                v_model=("mnt_opacity", 1.0),
                min=0,
                max=1,
                step=0.1,
                label="Satellite image opacity",
                classes="mt-1",
                hide_details=True,
                style="max-width: 400px",
                dense=True,
            )
            vuetify.VSpacer()   
            vuetify.VCheckbox(
                key="0",
                label="CMD map",
                v_model=("visibilityCMD[0]",),
                change=(update_CMD_visibility, "[$event]"),
            )
            vuetify.VSlider(
                # Opacity
                v_model=("cmd_opacity", 1.0),
                min=0,
                max=1,
                step=0.1,
                label="CMD map opacity",
                classes="mt-1",
                hide_details=True,
                style="max-width: 400px",
                dense=True,
            )
            
def scale_card():
    with ui_card(title="Colormap settings", ui_name="Settings"):
        vuetify.VSpacer()
        
        with vuetify.VCol():    
            vuetify.VRangeSlider(
                thumb_size=16,
                thumb_label=True,
                label="Velocity",
                v_model=("vel_range", [vel_range[0], vel_range[1]]),
                min=(str(vel_range[0]),),
                max=(str(vel_range[1]),),
                step = (vel_range[1] - vel_range[0])/50,
                # dense=True,
                rounded=True,
                hide_details=True,
                style="width: 400px",
            )
            vuetify.VSpacer()  
            vuetify.VRangeSlider(
                thumb_size=16,
                thumb_label=True,
                label="Resistivity",
                v_model=("res_range", [res_range[0], res_range[1]]),
                min=(str(res_range[0]),),
                max=(str(res_range[1]),),
                step = (res_range[1] - res_range[0])/50,
                # dense=True,
                rounded=True,
                hide_details=True,
                style="width: 400px",
            )
#---------------------------------
# Callbacks
# --------------------------------

###################
# mesh[O] dans la definition de la fonction (va savoir pourquoi)
# boucle sur tous les actors 
###################

@state.change("vel_range")
def set_vel_range(vel_range=mesh[0].get_data_range(arr_var='Velocity'), **kwargs):
    for j in range(len(mesh)):
        actor_profile[j].mapper.scalar_range = vel_range
    ctrl.view_update()
    
@state.change("res_range")
def set_res_range(res_range=mesh_cmd.get_data_range(arr_var='Resistivity'), **kwargs):
    actor_cmd[0].mapper.scalar_range = res_range
    ctrl.view_update()

@state.change("mnt_opacity")
def update_opacity_dem(mnt_opacity, **kwargs):
    actor_dem[0].GetProperty().SetOpacity(mnt_opacity)
    ctrl.view_update()
    
@state.change("cmd_opacity")
def update_opacity_cmd(cmd_opacity, **kwargs):
    actor_cmd[0].GetProperty().SetOpacity(cmd_opacity)
    ctrl.view_update()
    
# Visibility Change
def visibility_change(event):
    _id = event["id"]
    _visibility = event["visible"]

    if _id == "1":  
        for i in range(len(mesh)):
            update_profile_visibility(i, _visibility)
    elif _id == "2":  
        update_DEM_visibility(_visibility)
        update_CMD_visibility(_visibility)     
            
    ctrl.view_update()

#---------------------------------
# Gui
# --------------------------------
def pipeline_widget():
    trame.GitTree(
        sources=(
            "pipeline",
            [
                {"id": "1", "parent": "0", "visible": 1, "name": "Geophysical profiles"},
                {"id": "2", "parent": "1", "visible": 1, "name": "Images and maps"},
                {"id": "3", "parent": "2", "visible": 1, "name": "Colormap settings"},
            ],
        ),
        actives_change=(actives_change, "[$event]"),
        visibility_change=(visibility_change, "[$event]"),
    )

# -----------------------------------------------------------------------------
# Page web + toolbar init /GUI
# -----------------------------------------------------------------------------


with SinglePageWithDrawerLayout(server) as layout:
    
    layout.icon.click = ctrl.view_reset_camera
    layout.title.set_text(state.trame__title)

    # Draw mesh in main actor
    for i in range(len(mesh)):
        ghosts = np.argwhere(mesh[i]['S_Coverage'] == 0)
        mesh_clean = mesh[i].remove_cells(ghosts)
        mesh_profile_plot = pl.add_mesh(mesh_clean,scalars='Velocity',cmap=seismic_cm, 
                            lighting=False, scalar_bar_args=sargs_seismic,
                            )
        actor_profile.append(mesh_profile_plot)
    
    mesh_dem_plot = pl.add_mesh(mesh_aerial, texture=texture, opacity=0.7, 
                                cmap=elevation_cm, scalar_bar_args=sargs_dem, 
                                lighting=False,
                                )
    actor_dem.append(mesh_dem_plot)
    
    mesh_cmd_plot = pl.add_mesh(mesh=mesh_cmd, scalars='Resistivity', 
                                cmap=resistivity_cm, opacity=1, 
                                scalar_bar_args=sargs_cmd, 
                                nan_opacity=0., lighting=False, 
                                )
    actor_cmd.append(mesh_cmd_plot)

    pl.reset_camera()

    
    with layout.toolbar:
        vuetify.VSpacer()
         
    with layout.drawer:
        pipeline_widget()
        vuetify.VDivider(classes="mb-2")
        mesh_card()
        maps_card()
        scale_card()
        
    with layout.content:
            with vuetify.VContainer(
                fluid=True,
                classes="pa-0 fill-height",
            ):
                # Use PyVista UI template for Plotters
                view = plotter_ui(pl)
                
                ctrl.view_update = view.update
                
server.start()