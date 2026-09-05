"""Configuração compartilhada dos testes: garante que `src` seja importável
ao rodar `pytest` a partir do diretório `agencia/`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
