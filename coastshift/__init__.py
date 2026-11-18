"""CoastShift — modelagem espacialmente explícita da elevação do nível do mar (costa da Bahia).

Modelos:
  O1  bathtub hidraulicamente conectado
  O2  estático probabilístico (Monte Carlo: AR6 + extremos + ondas + erro do DEM)
  O3  hidrodinâmica reduzida 2D (inercial local, Bates et al., 2010)
  O4  costa e habitats (Bruun + quadro de maré para manguezal + inundação amplificada)
  O5  integrado probabilístico (biblioteca O3 + emulador + danos/EAD)
"""
__version__ = "1.0.0"
