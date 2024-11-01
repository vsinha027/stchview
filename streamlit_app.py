import streamlit as st
import numpy as np
from io import StringIO
import pandas as pd
import streamlit.components.v1 as components
import subprocess
import tempfile
import os
# import sys

# def install(package):
#     subprocess.check_call([sys.executable, "-m", "pip", "install", package])
# install('rdkit')
# install('py3Dmol')

import py3Dmol
from rdkit import Chem
from rdkit.Chem import AllChem
# Define the showmol function
def showmol(view, width=800, height=500):
    """
    Renders the py3Dmol viewer in a Streamlit app
    """
    view.zoomTo()
    html = view._make_html()
    components.html(html, width=width, height=height)

def render_mol(xyz, show_labels=False, show_indices=False, view="CPK"):
    xyzview = py3Dmol.view(width=800, height=400)
    xyzview.addModel(xyz, "xyz")
    
    if view == "CPK":
        xyzview.setStyle({'stick':{}, 'sphere':{'radius':0.5}})
    elif view == "VdW":
        xyzview.setStyle({'sphere':{}})
    
    if show_labels or show_indices:
        atoms, coordinates, _ = parse_xyz_string(xyz)
        if show_labels:
            for atom, coord in zip(atoms, coordinates):
                xyzview.addLabel(atom, {'position': {'x': coord[0]-0.05, 'y': coord[1]-0.05, 'z': coord[2]-0.05},
                                      'fontColor': 'red', 'alignment': 'center'})
        if show_indices:
            for i, coord in enumerate(coordinates):
                xyzview.addLabel(f"{i+1}", {'position': {'x': coord[0], 'y': coord[1], 'z': coord[2]},
                                          'fontColor': 'red', 'alignment': 'center',
                                          'offset': {'x': 1, 'y': 0, 'z': 0}})
    
    xyzview.zoomTo()
    showmol(xyzview, height=400, width=800)

@st.cache_data
def parse_xyz_string(xyz_string):
    lines = xyz_string.strip().split('\n')
    num_atoms = int(lines[0])
    comment = lines[1]
    atoms = []
    coordinates = []
    
    for i in range(2, num_atoms+2):
        if lines[i].strip():
            atom_data = lines[i].split()
            atoms.append(atom_data[0])
            coordinates.append([float(x) for x in atom_data[1:4]])
    
    return atoms, coordinates, comment

@st.cache_data
def write_xyz_string(atoms, coordinates, comment="Generated by Streamlit app"):
    xyz_content = f"{len(atoms)}\n{comment}\n"
    for atom, coord in zip(atoms, coordinates):
        xyz_content += f"{atom} {coord[0]:.6f} {coord[1]:.6f} {coord[2]:.6f}\n"
    return xyz_content

@st.cache_data
def parse_trajectory_xyz(xyz_string):
    """Parse a multi-structure XYZ file into a list of (atoms, coordinates) tuples"""
    structures = []
    lines = xyz_string.strip().split('\n')
    
    i = 0
    while i < len(lines):
        try:
            num_atoms = int(lines[i])
            comment = lines[i+1]
            atoms = []
            coordinates = []
            
            for j in range(i+2, i+2+num_atoms):
                if j < len(lines):
                    atom_data = lines[j].split()
                    if len(atom_data) >= 4:
                        atoms.append(atom_data[0])
                        coordinates.append([float(x) for x in atom_data[1:4]])
            
            if atoms and coordinates:
                structures.append((atoms, coordinates))
            
            i += num_atoms + 2
        except (ValueError, IndexError):
            i += 1
    
    return structures

@st.cache_data
def get_trajectory_from_xtb(tmpdir):
    try:
        with open(os.path.join(tmpdir, "xtbopt.log"), 'r') as f:
            trajectory_content = f.read()
        return trajectory_content
    except FileNotFoundError:
        st.error("Trajectory file not found")
        return None

@st.cache_data
def run_xtb_optimization(xyz_content):
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "input.xyz")
        with open(input_file, "w") as f:
            f.write(xyz_content)
        
        try:
            subprocess.run(["xtb", input_file, "--opt"], cwd=tmpdir, check=True)
            
            with open(os.path.join(tmpdir, "xtbopt.xyz"), "r") as f:
                optimized_xyz = f.read()
            
            trajectory_xyz = get_trajectory_from_xtb(tmpdir)
            
            return optimized_xyz, trajectory_xyz
        except subprocess.CalledProcessError:
            return None, None
        except FileNotFoundError:
            st.error("xTB is not installed or not in PATH")
            return None, None

# Set page config
st.set_page_config(page_title="Molecular Viewer", layout="wide")

# Initialize session state
if 'optimized_xyz' not in st.session_state:
    st.session_state.optimized_xyz = None
if 'trajectory_xyz' not in st.session_state:
    st.session_state.trajectory_xyz = None
if 'optimization_complete' not in st.session_state:
    st.session_state.optimization_complete = False

st.title("Molecular Viewer and Editor")

uploaded_file = st.file_uploader("Upload XYZ file", type="xyz")
if uploaded_file:
    xyz_string = uploaded_file.getvalue().decode()
    atoms, coordinates, comment = parse_xyz_string(xyz_string)
    
    # Create DataFrame for coordinates
    df = pd.DataFrame({
        'Atom': atoms,
        'X': [coord[0] for coord in coordinates],
        'Y': [coord[1] for coord in coordinates],
        'Z': [coord[2] for coord in coordinates]
    })
    
    # Display and edit coordinates
    st.subheader("Atomic Coordinates")
    edited_df = st.data_editor(df)
    
    # Update coordinates from edited DataFrame
    atoms = edited_df['Atom'].tolist()
    coordinates = edited_df[['X', 'Y', 'Z']].values.tolist()
    
    # View type selection
    view_type = st.selectbox('Choose view type', ("CPK", "VdW"))
    
    # Molecular viewer
    st.subheader("Molecular Viewer")
    
    # Toggle buttons
    col1, col2 = st.columns(2)
    with col1:
        show_labels = st.toggle("Show Atom Labels")
    with col2:
        show_indices = st.toggle("Show Atom Indices")
    
    # Create XYZ string for viewer and render molecule
    xyz_string = write_xyz_string(atoms, coordinates)
    render_mol(xyz_string, show_labels, show_indices, view_type)
    
    # Run xTB optimization
    if st.button("Run GFN2-xTB Optimization"):
        with st.spinner("Running optimization..."):
            optimized_xyz, trajectory_xyz = run_xtb_optimization(xyz_string)
            if optimized_xyz:
                st.session_state.optimized_xyz = optimized_xyz
                st.session_state.trajectory_xyz = trajectory_xyz
                st.session_state.optimization_complete = True
                st.rerun()
            else:
                st.error("Optimization failed. Please check if xTB is installed correctly.")
    
    # Show optimization results if available
    if st.session_state.optimization_complete:
        st.success("Optimization completed!")
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Download optimized structure",
                data=st.session_state.optimized_xyz,
                file_name="optimized.xyz",
                mime="chemical/x-xyz"
            )
        
        # Show optimized structure
        st.subheader("Optimized Structure")
        render_mol(st.session_state.optimized_xyz, show_labels, show_indices, view_type)
        
        # Trajectory visualization
        if st.session_state.trajectory_xyz:
            st.subheader("Optimization Trajectory")
            
            st.download_button(
                label="Download complete trajectory",
                data=st.session_state.trajectory_xyz,
                file_name="trajectory.xyz",
                mime="chemical/x-xyz"
            )
            
            # Parse trajectory
            trajectory_structures = parse_trajectory_xyz(st.session_state.trajectory_xyz)
            
            if trajectory_structures:
                # Trajectory viewer
                step = st.slider("Trajectory Step", 0, len(trajectory_structures)-1, 0)
                
                # Create XYZ string for selected trajectory step
                step_atoms, step_coordinates = trajectory_structures[step]
                step_xyz = write_xyz_string(step_atoms, step_coordinates)
                render_mol(step_xyz, show_labels, show_indices, view_type)
                
                st.text(f"Showing structure {step+1} of {len(trajectory_structures)}")
else:
    st.info("Please upload an XYZ file to start.")
