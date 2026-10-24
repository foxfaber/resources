#!/bin/sh
# Filiera completa: capitoli -> folii/testatine -> indice -> preliminari -> volume cucito.
set -e
cd "$(dirname "$0")/.."
echo "1. impaginazione capitoli"; node build/costruisci.js capitoli
echo "2. folii e testatine";      python3 build/impagina.py stampa
echo "3. preliminari con indice"; node build/costruisci.js preliminari
echo "4. cucitura";               python3 build/impagina.py unisci
