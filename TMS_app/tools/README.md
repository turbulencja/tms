# TMS app
This is an application dedicated to processing sets of electro-chemical 
and optical data.

## Table of contents
* [General info](#general-info)
* [Technologies](#technologies)
* [Requirements](#requirements)
* [Manual Mode](#manual-mode)
* [Experiment Mode](#experiment-mode)

## General info
The project has been developed with funding from TechMatStrateg program.

## Technologies
Application is built entirely based on Python 3.

## Requirements
Application has been developed and tested on Windows 7. 

## Manual mode
Manual mode is dedicated to single-measurement analysis. The naming convention of the files doesn't matter.
A possibility of saving additional analysis files is available for each cycle:
* boundary spectra file with optical measurements corresponding to Vmin, Vmax and both Vmid of electrochemical measurement
* cycle file with U [V], I [A], fit lambda [nm], and IODM coefficient with information on the wavelength range it had been calculated with.

## Experiment mode
The experiment mode allows for walking through a directory tree. Each directory is scanned for two files that conform 
to the following naming convention:
* optical measurement file starting with "opto_" and ending with ".csv"
* electrochemical file starting with "ech_pr_" and ending with ".csv"

All additional analysis files are being saved in the respective directory.