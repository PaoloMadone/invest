"""
Script de test pour le service de prix
"""

from price_service import PriceService

def test_price_service():
    service = PriceService()
    
    print("Test du service de prix...")
    
    # Test crypto BTC
    print("\n1. Test prix Bitcoin (BTC):")
    btc_price = service.get_crypto_price("BTC")
    if btc_price:
        print(f"   Prix BTC: {btc_price:,.2f}€")
    else:
        print("   Erreur: Impossible de récupérer le prix BTC")
    
    # Test action (exemple fictif)
    print("\n2. Test prix action AAPL:")
    aapl_price = service.get_stock_price("AAPL")
    if aapl_price:
        print(f"   Prix AAPL: {aapl_price:.2f}€")
    else:
        print("   Erreur: Impossible de récupérer le prix AAPL")
    
    # Test calcul de performance
    print("\n3. Test calcul de performance:")
    test_investments = [
        {
            'symbole': 'BTC',
            'prix_unitaire': 90000.0,
            'quantite': 0.001,
            'montant': 90.0
        }
    ]
    
    performances = service.calculate_investment_performance(test_investments, 'crypto')
    for perf in performances:
        if perf.get('prix_recupere'):
            print(f"   Investissement BTC:")
            print(f"   - Prix d'achat: {perf['prix_unitaire']:,.0f}€")
            print(f"   - Prix actuel: {perf['prix_actuel']:,.0f}€")
            print(f"   - P&L: {perf['pnl_montant']:+.2f}€ ({perf['pnl_pourcentage']:+.1f}%)")
        else:
            print("   Impossible de récupérer les prix pour le test")

if __name__ == "__main__":
    test_price_service()