#!/usr/bin/env python3
"""
Script pour exécuter les tests de l'application d'investissement
Usage: python run_tests.py
"""

import subprocess
import sys
import os

def install_pytest_if_missing():
    """Installe pytest si pas déjà installé"""
    try:
        import pytest
        print("pytest est deja installe")
    except ImportError:
        print("pytest n'est pas installe, installation en cours...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pytest"])
        print("pytest installe avec succes")

def run_tests():
    """Exécute tous les tests"""
    print("\n" + "="*50)
    print("EXECUTION DES TESTS D'INVESTISSEMENT")
    print("="*50)
    
    # Installation de pytest si nécessaire
    install_pytest_if_missing()
    
    # Exécution des tests
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "test_app.py", 
            "-v",
            "--tb=short"
        ], capture_output=True, text=True)
        
        print("\nRESULTATS DES TESTS:")
        print("-" * 30)
        print(result.stdout)
        
        if result.stderr:
            print("\nERREURS/AVERTISSEMENTS:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("\nTOUS LES TESTS SONT PASSES!")
            print("- Ajout de revenus: OK")
            print("- Ajout d'investissements bourse: OK") 
            print("- Ajout d'investissements crypto: OK")
            print("- Calculs de budget: OK")
        else:
            print(f"\nECHEC DES TESTS (code: {result.returncode})")
            print("Veuillez corriger les erreurs avant de continuer le développement.")
            
        return result.returncode == 0
        
    except FileNotFoundError:
        print("Erreur: pytest non trouve")
        return False
    except Exception as e:
        print(f"Erreur lors de l'execution des tests: {e}")
        return False

def run_specific_test_category(category):
    """Exécute une catégorie spécifique de tests"""
    categories = {
        "revenus": "TestRevenusOperations",
        "bourse": "TestBourseOperations", 
        "crypto": "TestCryptoOperations",
        "budget": "TestCalculsBudget",
        "validation": "TestValidationDonnees"
    }
    
    if category not in categories:
        print(f"Categorie inconnue: {category}")
        print(f"Categories disponibles: {', '.join(categories.keys())}")
        return False
    
    class_name = categories[category]
    print(f"\nTests pour: {category.upper()}")
    print("-" * 30)
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            f"test_app.py::{class_name}",
            "-v"
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"Erreur: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Exécution d'une catégorie spécifique
        category = sys.argv[1].lower()
        success = run_specific_test_category(category)
    else:
        # Exécution de tous les tests
        success = run_tests()
    
    sys.exit(0 if success else 1)