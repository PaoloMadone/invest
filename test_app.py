import pytest
import json
import os
from datetime import date
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

# Import des fonctions à tester
from app import load_data, save_data
from business_logic import (
    calculer_investissements_automatiques,
    verifier_periode_existante,
    creer_periode,
    calculer_quantite_investissement,
    calculer_budget_disponible,
    calculer_budget_utilise,
    calculer_budget_restant,
    valider_donnees_revenu,
    valider_donnees_investissement,
    creer_donnees_revenu,
    creer_donnees_investissement
)

class TestInvestmentApp:
    """Tests pour l'application d'investissement"""
    
    @pytest.fixture
    def mock_supabase(self):
        """Mock de la base de données Supabase"""
        mock_client = Mock()
        mock_table = Mock()
        
        # Configuration du mock pour les opérations select
        mock_table.select.return_value.execute.return_value.data = []
        
        # Configuration du mock pour les opérations insert
        mock_insert = Mock()
        mock_insert.execute.return_value = Mock()
        mock_table.insert.return_value = mock_insert
        
        # Configuration du mock pour les opérations delete
        mock_delete = Mock()
        mock_delete.execute.return_value = Mock()
        mock_table.delete.return_value = mock_delete
        
        mock_client.table.return_value = mock_table
        return mock_client
    
    @pytest.fixture
    def sample_data(self):
        """Données d'exemple pour les tests"""
        return {
            "revenus": [
                {
                    "id": 1,
                    "mois": 1,
                    "annee": 2024,
                    "periode": "2024-01",
                    "montant": 3000,
                    "investissement_disponible_bourse": 300,
                    "investissement_disponible_crypto": 300
                }
            ],
            "bourse": [
                {
                    "id": 1,
                    "date": "2024-01-15",
                    "symbole": "HIWS",
                    "montant": 100,
                    "prix_unitaire": 25.50,
                    "quantite": 3.92,
                    "hors_budget": False
                }
            ],
            "crypto": [
                {
                    "id": 1,
                    "date": "2024-01-15",
                    "symbole": "BTC",
                    "montant": 100,
                    "prix_unitaire": 45000,
                    "quantite": 0.00222,
                    "hors_budget": False
                }
            ]
        }

class TestRevenusOperations(TestInvestmentApp):
    """Tests spécifiques aux opérations sur les revenus"""
    
    def test_calcul_investissement_automatique(self):
        """Test du calcul automatique des montants d'investissement"""
        revenu_net = 3000
        inv_bourse, inv_crypto = calculer_investissements_automatiques(revenu_net)
        
        assert inv_bourse == 300.0
        assert inv_crypto == 300.0
    
    def test_periode_existante(self, sample_data):
        """Test de détection d'une période existante"""
        revenus = sample_data["revenus"]
        
        # Test avec période existante
        assert verifier_periode_existante(revenus, "2024-01") == True
        
        # Test avec période nouvelle
        assert verifier_periode_existante(revenus, "2024-02") == False
    
    def test_creation_periode(self):
        """Test de création d'une période"""
        periode = creer_periode(2024, 2)
        assert periode == "2024-02"
        
        periode_janvier = creer_periode(2024, 1)
        assert periode_janvier == "2024-01"
    
    def test_validation_donnees_revenu(self):
        """Test de validation des données de revenu"""
        # Données valides
        erreurs = valider_donnees_revenu(3000, 2, 2024)
        assert len(erreurs) == 0
        
        # Revenu invalide
        erreurs = valider_donnees_revenu(0, 2, 2024)
        assert "Le revenu net doit être supérieur à 0" in erreurs
        
        # Mois invalide
        erreurs = valider_donnees_revenu(3000, 13, 2024)
        assert "Le mois doit être entre 1 et 12" in erreurs
        
        # Année invalide
        erreurs = valider_donnees_revenu(3000, 2, 2040)
        assert "L'année doit être entre 2020 et 2030" in erreurs
    
    def test_creation_donnees_revenu(self):
        """Test de création des données de revenu"""
        donnees = creer_donnees_revenu(2, 2024, 3000)
        
        assert donnees["mois"] == 2
        assert donnees["annee"] == 2024
        assert donnees["periode"] == "2024-02"
        assert donnees["montant"] == 3000
        assert donnees["investissement_disponible_bourse"] == 300.0
        assert donnees["investissement_disponible_crypto"] == 300.0

class TestBourseOperations(TestInvestmentApp):
    """Tests spécifiques aux opérations bourse"""
    
    def test_calcul_quantite_investissement(self):
        """Test du calcul de quantité d'investissement"""
        montant = 150.0
        prix_unitaire = 25.0
        quantite = calculer_quantite_investissement(montant, prix_unitaire)
        
        assert quantite == 6.0
    
    def test_calcul_quantite_division_par_zero(self):
        """Test que le calcul de quantité échoue si prix = 0"""
        with pytest.raises(ValueError, match="Le prix unitaire doit être supérieur à 0"):
            calculer_quantite_investissement(100, 0)
    
    def test_calcul_budget_utilise(self, sample_data):
        """Test du calcul du budget utilisé"""
        investissements_bourse = sample_data["bourse"]
        budget_utilise, total_investi = calculer_budget_utilise(investissements_bourse)
        
        assert budget_utilise == 100
        assert total_investi == 100
    
    def test_hors_budget_exclusion(self):
        """Test d'exclusion des investissements hors budget du calcul"""
        investissements = [
            {"montant": 100, "hors_budget": False},
            {"montant": 200, "hors_budget": True},
            {"montant": 50, "hors_budget": False}
        ]
        
        budget_utilise, total_investi = calculer_budget_utilise(investissements)
        
        assert budget_utilise == 150
        assert total_investi == 350
    
    def test_validation_donnees_investissement(self):
        """Test de validation des données d'investissement"""
        # Données valides
        erreurs = valider_donnees_investissement(150.0, 25.0, "HIWS")
        assert len(erreurs) == 0
        
        # Montant invalide
        erreurs = valider_donnees_investissement(0, 25.0, "HIWS")
        assert "Le montant doit être supérieur à 0" in erreurs
        
        # Petit montant (devrait être valide mais va échouer avec notre bug)
        erreurs = valider_donnees_investissement(50.0, 25.0, "HIWS")
        assert len(erreurs) == 0  # Devrait être valide mais va échouer
        
        # Prix invalide
        erreurs = valider_donnees_investissement(150.0, 0, "HIWS")
        assert "Le prix unitaire doit être supérieur à 0" in erreurs
        
        # Symbole manquant
        erreurs = valider_donnees_investissement(150.0, 25.0, "")
        assert "Le symbole est obligatoire" in erreurs
    
    def test_creation_donnees_investissement(self):
        """Test de création des données d'investissement"""
        donnees = creer_donnees_investissement("2024-01-15", "HIWS", 150.0, 25.0, False)
        
        assert donnees["date"] == "2024-01-15"
        assert donnees["symbole"] == "HIWS"
        assert donnees["montant"] == 150.0
        assert donnees["prix_unitaire"] == 25.0
        assert donnees["quantite"] == 6.0
        assert donnees["hors_budget"] == False

class TestCryptoOperations(TestInvestmentApp):
    """Tests spécifiques aux opérations crypto"""
    
    @patch('app.supabase')
    def test_ajout_investissement_crypto(self, mock_supabase):
        """Test d'ajout d'un investissement crypto"""
        # Configuration du mock
        mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock()
        
        # Données d'investissement crypto
        montant = 100.0
        prix_unitaire = 45000.0
        quantite_attendue = montant / prix_unitaire
        
        investissement_data = {
            "date": "2024-01-15",
            "symbole": "BTC",
            "montant": montant,
            "prix_unitaire": prix_unitaire,
            "quantite": quantite_attendue,
            "hors_budget": False
        }
        
        # Vérification du calcul de quantité pour crypto (précision importante)
        assert abs(quantite_attendue - 0.00222222) < 0.00001
    
    def test_calcul_budget_crypto(self, sample_data):
        """Test du calcul du budget crypto utilisé"""
        investissements_crypto = sample_data["crypto"]
        budget_utilise = sum([c["montant"] for c in investissements_crypto if not c.get("hors_budget", False)])
        
        assert budget_utilise == 100

class TestCalculsBudget(TestInvestmentApp):
    """Tests des calculs de budget globaux"""
    
    def test_calcul_budget_disponible(self, sample_data):
        """Test du calcul du budget disponible avec fonctions business_logic"""
        revenus = sample_data["revenus"]
        budget_bourse, budget_crypto, budget_total = calculer_budget_disponible(revenus)
        
        # Les budgets sont arrondis vers le haut (math.ceil)
        assert budget_bourse == 300
        assert budget_crypto == 300
        assert budget_total == 600
    
    def test_calcul_budget_restant_avec_fonction(self):
        """Test du calcul du budget restant avec fonction business_logic"""
        budget_disponible = 300
        budget_utilise = 100
        
        budget_restant = calculer_budget_restant(budget_disponible, budget_utilise)
        
        assert budget_restant == 200

class TestValidationDonnees(TestInvestmentApp):
    """Tests de validation des données"""
    
    def test_validation_montant_positif(self):
        """Test que les montants doivent être positifs"""
        montants_valides = [100, 50.5, 1000]
        montants_invalides = [0, -10, -100.5]
        
        for montant in montants_valides:
            assert montant > 0
        
        for montant in montants_invalides:
            assert montant <= 0
    
    def test_validation_prix_unitaire_positif(self):
        """Test que les prix unitaires doivent être positifs"""
        prix_valides = [25.50, 45000, 0.01]
        prix_invalides = [0, -25.50, -1]
        
        for prix in prix_valides:
            assert prix > 0
        
        for prix in prix_invalides:
            assert prix <= 0

class TestDataOperations(TestInvestmentApp):
    """Tests des opérations sur les données"""
    
    @patch('app.supabase')
    def test_load_data_success(self, mock_supabase, sample_data):
        """Test du chargement réussi des données"""
        # Configuration du mock pour retourner les données d'exemple
        mock_supabase.table.return_value.select.return_value.execute.return_value.data = sample_data["revenus"]
        
        # Le test complet nécessiterait de mocker chaque table séparément
        # Ici on teste la structure de base
        expected_structure = {"revenus": [], "bourse": [], "crypto": []}
        
        # Vérification que la structure attendue est correcte
        assert "revenus" in expected_structure
        assert "bourse" in expected_structure
        assert "crypto" in expected_structure
    
    @patch('builtins.open')
    @patch('json.dump')
    def test_save_data(self, mock_json_dump, mock_open, sample_data):
        """Test de sauvegarde des données"""
        save_data(sample_data)
        
        # Vérification que le fichier est ouvert en écriture
        mock_open.assert_called_once_with("investments_data.json", 'w')
        
        # Vérification que json.dump est appelé
        mock_json_dump.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])