"""
Test d'intégration pour valider toute la chaîne fonctionnelle :
- Ajout d'un revenu
- Achat d'un investissement bourse et crypto  
- Vente partielle
- Validation des calculs PnL et positions restantes

Ce test simule un workflow complet sans utiliser Supabase.
"""

import json
import tempfile
import os
from datetime import date
from unittest.mock import Mock, patch

import pytest

from business_logic import (
    calculer_investissements_automatiques,
    creer_donnees_revenu,
    creer_donnees_investissement,
    creer_donnees_vente,
    valider_donnees_vente,
    calculer_quantite_disponible,
    calculer_positions_restantes_fifo,
)
from price_service import PriceService


class TestIntegration:
    """Tests d'intégration pour valider le workflow complet"""

    def setup_method(self):
        """Setup pour chaque test"""
        self.mock_supabase = Mock()
        self.price_service = PriceService(self.mock_supabase)
        
        # Mock des prix pour les tests
        self.mock_prices = {
            "AAPL": 150.0,
            "BTC": 45000.0,
        }
        
    def mock_get_current_price(self, symbol, asset_type, show_log=True):
        """Mock pour récupérer les prix"""
        return self.mock_prices.get(symbol)

    def test_workflow_complet_bourse(self):
        """
        Test du workflow complet pour la bourse :
        1. Créer un revenu
        2. Acheter une action AAPL à 100€
        3. Vendre 50% à 150€ 
        4. Valider les calculs PnL et positions
        """
        print("\n=== TEST WORKFLOW COMPLET BOURSE ===")
        
        # 1. Créer un revenu de 3000€
        revenu_data = creer_donnees_revenu(1, 2024, 3000.0)
        budget_bourse = revenu_data["investissement_disponible_bourse"]
        
        print(f"OK Revenu créé : {revenu_data['montant']}€")
        print(f"OK Budget bourse disponible : {budget_bourse}€")
        assert budget_bourse == 300.0  # 10% de 3000€
        
        # 2. Acheter 2 actions AAPL à 100€ chacune (200€ total)
        achat_data = creer_donnees_investissement(
            "2024-01-15",
            "AAPL", 
            200.0,  # 200€
            100.0,  # 100€ par action
            False
        )
        
        print(f"OK Achat créé : {achat_data['quantite']} actions à {achat_data['prix_unitaire']}€")
        print(f"DEBUG Achat après création: {achat_data}")
        assert achat_data["quantite"] == 2.0
        assert achat_data["symbole"] == "AAPL"
        
        # Simuler la base de données avec nos données (faire une copie)
        import copy
        investments_db = [copy.deepcopy(achat_data)]
        print(f"DEBUG Achat après copie dans DB: {investments_db[0]}")
        
        # 3. Vérifier la quantité disponible
        quantite_dispo = calculer_quantite_disponible(investments_db, "AAPL")
        print(f"OK Quantité disponible avant vente : {quantite_dispo}")
        assert quantite_dispo == 2.0
        
        # 4. Vendre 1 action à 150€ (gain de 50€)
        erreurs_vente = valider_donnees_vente(
            150.0,  # montant vente
            150.0,  # prix unitaire vente
            "AAPL",
            1.0,    # quantité à vendre
            investments_db
        )
        assert len(erreurs_vente) == 0, f"Erreurs de validation : {erreurs_vente}"
        
        vente_data = creer_donnees_vente(
            "2024-02-15",
            "AAPL",
            150.0,  # 150€
            150.0   # 150€ par action
        )
        
        print(f"OK Vente créée : {vente_data['quantite']} actions à {vente_data['prix_unitaire']}€")
        investments_db.append(vente_data)
        
        # 5. Vérifier la quantité après vente
        quantite_dispo_apres = calculer_quantite_disponible(investments_db, "AAPL")
        print(f"OK Quantité disponible après vente : {quantite_dispo_apres}")
        assert quantite_dispo_apres == 1.0  # 2 - 1 = 1
        
        # 6. Tester le calcul PnL réalisé via FIFO
        with patch.object(self.price_service, 'get_current_price', self.mock_get_current_price):
            pnl_data = self.price_service.calculate_realized_pnl(investments_db, "AAPL")
        
        print(f"OK PnL réalisé : {pnl_data['pnl_realise_montant']}€")
        print(f"OK PnL réalisé % : {pnl_data['pnl_realise_pourcentage']:.1f}%")
        
        # Vérifications PnL : vente 1 action à 150€, achetée à 100€ = +50€
        assert pnl_data["pnl_realise_montant"] == 50.0
        assert pnl_data["pnl_realise_pourcentage"] == 50.0  # (150-100)/100 * 100
        assert pnl_data["quantite_vendue_totale"] == 1.0
        
        # 7. Tester les positions restantes FIFO
        positions = calculer_positions_restantes_fifo(investments_db, "AAPL")
        print(f"OK Positions restantes : {len(positions)}")
        print(f"DEBUG Position data: {positions[0] if positions else 'No positions'}")
        print(f"DEBUG All investment data: {investments_db}")
        print(f"DEBUG Achat data: {achat_data}")
        print(f"DEBUG Vente data: {vente_data}")
        
        assert len(positions) == 1
        position = positions[0]
        assert position["quantite_initiale"] == 2.0
        assert position["quantite_restante"] == 1.0
        assert position["montant_restant"] == 100.0  # 1 action * 100€
        
        print("SUCCESS Test workflow bourse réussi !")

    def test_workflow_complet_crypto(self):
        """
        Test du workflow complet pour la crypto :
        1. Créer un revenu 
        2. Acheter du BTC
        3. Vendre une partie
        4. Valider les calculs
        """
        print("\n=== TEST WORKFLOW COMPLET CRYPTO ===")
        
        # 1. Créer un revenu de 5000€
        revenu_data = creer_donnees_revenu(2, 2024, 5000.0)
        budget_crypto = revenu_data["investissement_disponible_crypto"]
        
        print(f"OK Revenu créé : {revenu_data['montant']}€")
        print(f"OK Budget crypto disponible : {budget_crypto}€")
        assert budget_crypto == 500.0  # 10% de 5000€
        
        # 2. Acheter du BTC pour 400€ à 40000€ (0.01 BTC)
        achat_data = creer_donnees_investissement(
            "2024-02-01",
            "BTC",
            400.0,
            40000.0,
            False
        )
        
        print(f"OK Achat créé : {achat_data['quantite']} BTC à {achat_data['prix_unitaire']}€")
        assert achat_data["quantite"] == 0.01
        assert achat_data["symbole"] == "BTC"
        
        investments_db = [achat_data]
        
        # 3. Vendre 0.005 BTC à 50000€ (soit 250€)
        vente_data = creer_donnees_vente(
            "2024-03-01",
            "BTC", 
            250.0,  # 0.005 * 50000
            50000.0
        )
        
        investments_db.append(vente_data)
        print(f"OK Vente créée : {vente_data['quantite']} BTC à {vente_data['prix_unitaire']}€")
        
        # 4. Vérifier quantité disponible
        quantite_dispo = calculer_quantite_disponible(investments_db, "BTC")
        print(f"OK Quantité BTC disponible : {quantite_dispo}")
        assert abs(quantite_dispo - 0.005) < 0.001  # 0.01 - 0.005 = 0.005
        
        # 5. Test PnL réalisé
        with patch.object(self.price_service, 'get_current_price', self.mock_get_current_price):
            pnl_data = self.price_service.calculate_realized_pnl(investments_db, "BTC")
        
        print(f"OK PnL réalisé : {pnl_data['pnl_realise_montant']}€")
        
        # PnL : vente 0.005 BTC à 50000€ (250€) vs achat à 40000€ (200€) = +50€
        expected_pnl = 250.0 - 200.0  # (0.005 * 50000) - (0.005 * 40000)
        assert abs(pnl_data["pnl_realise_montant"] - expected_pnl) < 0.01
        
        print("SUCCESS Test workflow crypto réussi !")

    def test_scenario_multiple_achats_ventes(self):
        """
        Test d'un scénario complexe avec plusieurs achats et ventes FIFO
        """
        print("\n=== TEST SCENARIO COMPLEXE FIFO ===")
        
        investments_db = []
        
        # Achat 1: 100 actions à 10€ le 01/01
        achat1 = creer_donnees_investissement("2024-01-01", "XYZ", 1000.0, 10.0, False)
        investments_db.append(achat1)
        
        # Achat 2: 50 actions à 20€ le 01/02  
        achat2 = creer_donnees_investissement("2024-02-01", "XYZ", 1000.0, 20.0, False)
        investments_db.append(achat2)
        
        # Achat 3: 30 actions à 30€ le 01/03
        achat3 = creer_donnees_investissement("2024-03-01", "XYZ", 900.0, 30.0, False)
        investments_db.append(achat3)
        
        print("OK 3 achats créés : 100@10€, 50@20€, 30@30€")
        
        # Vente 1: 120 actions à 25€ le 01/04 (doit consommer achat1 complet + 20 de achat2)
        vente1 = creer_donnees_vente("2024-04-01", "XYZ", 3000.0, 25.0)
        investments_db.append(vente1)
        
        print("OK Vente 1 : 120 actions à 25€")
        
        # Test quantité disponible
        quantite_dispo = calculer_quantite_disponible(investments_db, "XYZ")
        print(f"OK Quantité disponible : {quantite_dispo}")
        assert quantite_dispo == 60.0  # 180 - 120 = 60
        
        # Test positions restantes FIFO
        positions = calculer_positions_restantes_fifo(investments_db, "XYZ")
        print(f"OK Positions restantes : {len(positions)}")
        
        # Vérifications FIFO :
        # - Achat1 (100@10€) : complètement vendu -> 0 restant
        # - Achat2 (50@20€) : 20 vendus -> 30 restant  
        # - Achat3 (30@30€) : pas touché -> 30 restant
        
        position_achat1 = next(p for p in positions if p["date"] == "2024-01-01")
        position_achat2 = next(p for p in positions if p["date"] == "2024-02-01") 
        position_achat3 = next(p for p in positions if p["date"] == "2024-03-01")
        
        assert position_achat1["quantite_restante"] == 0.0
        assert position_achat2["quantite_restante"] == 30.0  # 50 - 20
        assert position_achat3["quantite_restante"] == 30.0  # Pas touché
        
        # Test PnL réalisé
        with patch.object(self.price_service, 'get_current_price', lambda s, t, l=True: 25.0):
            pnl_data = self.price_service.calculate_realized_pnl(investments_db, "XYZ")
        
        # PnL attendu FIFO :
        # 100 actions vendues de achat1 : (25-10)*100 = +1500€
        # 20 actions vendues de achat2 : (25-20)*20 = +100€  
        # Total = +1600€
        expected_pnl = 1500.0 + 100.0
        print(f"OK PnL réalisé attendu : {expected_pnl}€")
        print(f"OK PnL réalisé calculé : {pnl_data['pnl_realise_montant']}€")
        
        assert abs(pnl_data["pnl_realise_montant"] - expected_pnl) < 0.01
        
        print("SUCCESS Test scenario complexe FIFO réussi !")

    def test_validation_erreurs(self):
        """Test des validations d'erreurs"""
        print("\n=== TEST VALIDATIONS ERREURS ===")
        
        # Test vente sans position
        erreurs = valider_donnees_vente(100.0, 10.0, "INEXISTANT", 1.0, [])
        assert len(erreurs) > 0
        print(f"OK Erreur vente sans position détectée : {erreurs[0]}")
        
        # Test vente quantité insuffisante
        achat_data = creer_donnees_investissement("2024-01-01", "TEST", 100.0, 10.0, False)
        erreurs = valider_donnees_vente(200.0, 10.0, "TEST", 20.0, [achat_data])  # Veut vendre 20, n'a que 10
        assert len(erreurs) > 0
        print(f"OK Erreur quantité insuffisante détectée : {erreurs[0]}")
        
        print("SUCCESS Test validations erreurs réussi !")

    def test_integration_performance_calculs(self):
        """Test d'intégration des calculs de performance"""
        print("\n=== TEST INTEGRATION PERFORMANCE ===")
        
        # Créer des investissements avec gains/pertes
        investments = [
            creer_donnees_investissement("2024-01-01", "GAIN", 100.0, 10.0, False),    # Sera en gain
            creer_donnees_investissement("2024-01-01", "LOSS", 100.0, 20.0, False),    # Sera en perte
        ]
        
        # Mock des prix actuels
        def mock_prices(symbol, asset_type, show_log=True):
            if symbol == "GAIN":
                return 15.0  # +50% (acheté 10€, vaut 15€)
            elif symbol == "LOSS":
                return 15.0  # -25% (acheté 20€, vaut 15€)
            return None
            
        with patch.object(self.price_service, 'get_current_price', mock_prices):
            # Test calcul performances
            perf_investments = self.price_service.calculate_investment_performance(investments, "bourse")
            
            gain_inv = next(inv for inv in perf_investments if inv["symbole"] == "GAIN")
            loss_inv = next(inv for inv in perf_investments if inv["symbole"] == "LOSS")
            
            print(f"OK GAIN - PnL: {gain_inv['pnl_montant']}€ ({gain_inv['pnl_pourcentage']:.1f}%)")
            print(f"OK LOSS - PnL: {loss_inv['pnl_montant']}€ ({loss_inv['pnl_pourcentage']:.1f}%)")
            
            # Vérifications
            assert gain_inv["pnl_montant"] == 50.0  # (15-10)*10
            assert gain_inv["pnl_pourcentage"] == 50.0
            assert loss_inv["pnl_montant"] == -25.0  # (15-20)*5  
            assert loss_inv["pnl_pourcentage"] == -25.0
            
            # Test résumé portfolio 
            portfolio_summary = self.price_service.calculate_portfolio_summary([], perf_investments)
            
            print(f"OK Portfolio total - PnL: {portfolio_summary['total']['pnl_montant']}€")
            assert portfolio_summary["total"]["pnl_montant"] == 25.0  # 50 - 25
            
        print("SUCCESS Test intégration performance réussi !")


def run_all_tests():
    """Lance tous les tests d'intégration"""
    test_runner = TestIntegration()
    
    print("DEMARRAGE DES TESTS D'INTEGRATION")
    print("=" * 50)
    
    tests = [
        test_runner.test_workflow_complet_bourse,
        test_runner.test_workflow_complet_crypto, 
        test_runner.test_scenario_multiple_achats_ventes,
        test_runner.test_validation_erreurs,
        test_runner.test_integration_performance_calculs
    ]
    
    for i, test_func in enumerate(tests, 1):
        try:
            test_runner.setup_method()
            test_func()
            print(f"OK Test {i}/{len(tests)} réussi")
        except Exception as e:
            print(f"ERREUR Test {i}/{len(tests)} échoué : {e}")
            raise
            
    print("\n" + "=" * 50)
    print("SUCCESS TOUS LES TESTS D'INTÉGRATION SONT PASSÉS ! SUCCESS")
    print("OK La chaîne fonctionnelle complète est validée")
    print("OK Ajouts d'investissements : OK")
    print("OK Ventes avec validation : OK") 
    print("OK Calculs PnL FIFO : OK")
    print("OK Gestion des erreurs : OK")
    print("OK Performances en temps réel : OK")


if __name__ == "__main__":
    run_all_tests()