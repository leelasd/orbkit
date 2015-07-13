# -*- coding: iso-8859-1 -*-
'''Module for processing the data read from the output files of quantum chemical 
software. '''
'''
orbkit
Gunter Hermann, Vincent Pohl, and Axel Schild

Institut fuer Chemie und Biochemie, Freie Universitaet Berlin, 14195 Berlin, Germany

This file is part of orbkit.

orbkit is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as 
published by the Free Software Foundation, either version 3 of 
the License, or any later version.

orbkit is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public 
License along with orbkit.  If not, see <http://www.gnu.org/licenses/>.
'''
#from scipy.constants import value as physical_constants
import numpy
from os import path


u_to_me = 1822.88839 # Contains the mass conversion factor to atomic units
nist_mass = None
# Standard atomic masses as "Linearized ASCII Output", see http://physics.nist.gov
nist_file = path.join(path.dirname(path.realpath(__file__)),
                      'supporting_data/Atomic_Weights_NIST.html')
# see http://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele=&all=all&ascii=ascii2&isotype=some

def read_nist():
  '''Reads and converts the atomic masses from the "Linearized ASCII Output", 
  see http://physics.nist.gov.
  '''
  global nist_mass
  
  f = open(nist_file,'r')
  flines = f.readlines()
  f.close()
  
  nist_mass = []
  index = None
  new = True
  
  def rm_brackets(text,rm=['(',')','[',']']):
    for i in rm:
      text = text.replace(i,'')
    return text
  
  for line in flines:
    thisline = line.split()
    if 'Atomic Number =' in line:
      i = int(thisline[-1]) - 1
      new = (i != index)
      if new:
        nist_mass.append(['',0])
      index = i
    elif 'Atomic Symbol =' in line and new:
      nist_mass[index][0] = thisline[-1]
    elif 'Standard Atomic Weight =' in line and new:
      nist_mass[index][1] = float(rm_brackets(thisline[-1]))

def standard_mass(atom):
  '''Returns the standard atomic mass of a given atom.
    
  **Parameters:**
  
  qc : int or str
    Contains the name or atomic number of the atom.
  
  **Returns:**
  
  mass : float
    Contains the atomic mass in atomic units.
  '''
  if nist_mass is None:
    read_nist()  
  try:
    atom = int(atom) - 1
    return nist_mass[atom][1] * u_to_me
  except ValueError:
    return dict(nist_mass)[atom.title()] * u_to_me
    
def get_atom_symbol(atom):
  '''Returns the atomic symbol of a given atom.
    
  **Parameters:**
  
  atom : int or str
    Contains the atomic number of the atom.
  
  **Returns:**
  
  symbol : float
    Contains the atomic symbol.
  '''
  if nist_mass is None:
    read_nist()  
  return nist_mass[int(atom)-1][0]  

class CIinfo:
  '''Class managing all information from the from the output 
  files of quantum chemical software for CI calculations.
  
  The CI related features are in ongoing development.
  '''
  def __init__(self,method='ci'):
    self.coeffs = []
    self.occ    = []
    self.info   = None
    self.method = method
  def copy(self):
    ciinfo = self.__class__(method=self.method)
    if self.coeffs != []:
      ciinfo.coeffs = numpy.copy(self.coeffs)
    if self.occ != []:
      ciinfo.occ = numpy.copy(self.occ)
    if self.info is not None:
      ciinfo.info = self.info.copy()    
    return ciinfo
  def todict(self):
    return self.__dict__
  def hdf5_save(self,fid='out.h5',group='/ci:0',mode='w'):
    from orbkit.output import hdf5_open,hdf5_append
    from copy import copy
    for hdf5_file in hdf5_open(fid,mode=mode):
      dct = copy(self.todict())
      dct['info'] = numpy.array(dct['info'].items(),dtype=str)
      hdf5_append(dct,hdf5_file,name=group)
  def hdf5_read(self,fid='out.h5',group='/ci:0'):
    from orbkit.output import hdf5_open,hdf52dict
    for hdf5_file in hdf5_open(fid,mode='r'):
      for key in self.__dict__.keys():
        try:
          self.__dict__[key] = hdf52dict('%s/%s' % (group,key),hdf5_file)
        except KeyError:
          self.__dict__[key] = hdf5_file['%s' % group].attrs[key]
      self.__dict__['info'] = dict(self.__dict__['info'])

class QCinfo:
  '''Class managing all information from the from the output 
  files of quantum chemical software.
  
  See :ref:`Central Variables` in the manual for details.
  '''
  def __init__(self):
    self.geo_spec = []
    self.geo_info = []
    self.ao_spec  = []
    self.ao_spherical = None
    self.mo_spec  = []
    self.etot     = 0.
    self.com      = 'Center of mass can be calculated with self.get_com().'
    self.coc      = 'Center of charge can be calculated with self.get_coc().'
    self.pop_ana  = {}
    # transition dipole information
    self.states         = {'multiplicity' : None,
                           'energy'       : None}
    self.dipole_moments = None
    
#    self.mo_coeff = None
#    self.mo_occup = None
#    self.mo_energ = None
#    self.mo_sym   = None

  def sort_mo_sym(self):
    '''Sorts mo_spec by symmetry.
    '''
    keys = []
    for i_mo in self.mo_spec:
      keys.append(i_mo['sym'].split('.'))
    keys = numpy.array(keys,dtype=int)
    self.mo_spec = list(numpy.array(self.mo_spec)[numpy.lexsort(keys.T)])

  def get_com(self,nuc_list=None):
    '''Computes the center of mass.
    '''
    self.com   = numpy.zeros(3)
    total_mass = 0.
    if nuc_list is None:
      nuc_list = range(len(self.geo_spec)) # iterate over all nuclei
    for ii in nuc_list:
      nuc_mass    = standard_mass(self.geo_info[ii][0])
      self.com   += numpy.multiply(self.geo_spec[ii],nuc_mass)
      total_mass += nuc_mass
    self.com = self.com/total_mass
    return self.com

  def get_coc(self):
    '''Computes the center of charge.
    '''
    self.coc     = numpy.zeros(3)
    total_charge = 0.
    for ii in range(len(self.geo_info)):
      nuc_charge    = float(self.geo_info[ii][2])
      self.coc     += numpy.multiply(self.geo_spec[ii],nuc_charge)
      total_charge += nuc_charge
    self.coc = self.coc/total_charge
    return self.coc
  
  def todict(self):
    '''Converts all essential variables into a dictionary.
    '''
    dct = {}
    keys = ['geo_spec',
            'geo_info',
            'ao_spec',
            'ao_spherical',
            'mo_spec']
    for key in keys:
      dct[key] = getattr(self,key)
    return dct
