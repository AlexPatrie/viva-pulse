"""Study figures for the workbench (Visualization v2 classes, one per module).

The workbench's env worker imports every submodule and registers each
``Visualization`` subclass; a study's ``visualizations[]`` entry wires store
paths to a class's input ports through ``config.inputs_map``.
"""
