"""
Service pour récupérer les prix en temps réel et calculer les performances
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
import yfinance as yf


class PriceService:
    """Service pour récupérer les prix des actifs et calculer les performances"""

    def __init__(self):
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        self.cache = {}
        self.cache_duration = 300  # 5 minutes

    def _is_cache_valid(self, symbol: str) -> bool:
        """Vérifie si le cache est encore valide pour un symbole donné"""
        if symbol not in self.cache:
            return False

        cache_time = self.cache[symbol].get("timestamp", 0)
        return time.time() - cache_time < self.cache_duration

    def get_crypto_price(self, symbol: str) -> Optional[float]:
        """
        Récupère le prix actuel d'une crypto via CoinGecko API

        Args:
            symbol: Symbole de la crypto (ex: 'BTC', 'ETH')

        Returns:
            Prix actuel en EUR ou None si erreur
        """
        symbol_lower = symbol.lower()

        # Vérifier le cache
        if self._is_cache_valid(f"crypto_{symbol_lower}"):
            return self.cache[f"crypto_{symbol_lower}"]["price"]

        try:
            # Mapping des symboles vers les IDs CoinGecko
            symbol_mapping = {
                "btc": "bitcoin",
                "eth": "ethereum",
                "ada": "cardano",
                "sol": "solana",
                "dot": "polkadot",
                "matic": "polygon",
                "avax": "avalanche-2",
                "atom": "cosmos",
                "link": "chainlink",
            }

            crypto_id = symbol_mapping.get(symbol_lower, symbol_lower)

            url = f"{self.coingecko_base_url}/simple/price"
            params = {"ids": crypto_id, "vs_currencies": "eur"}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if crypto_id in data and "eur" in data[crypto_id]:
                price = data[crypto_id]["eur"]

                # Mettre en cache
                self.cache[f"crypto_{symbol_lower}"] = {"price": price, "timestamp": time.time()}

                return price

            return None

        except requests.exceptions.RequestException as e:
            print(f"Erreur réseau lors de la récupération du prix crypto de {symbol}: {e}")
            return None
        except KeyError as e:
            print(f"Symbole crypto {symbol} non trouvé dans CoinGecko: {e}")
            return None
        except Exception as e:
            print(f"Erreur inattendue lors de la récupération du prix crypto de {symbol}: {e}")
            return None

    def get_stock_price(self, symbol: str) -> Optional[float]:
        """
        Récupère le prix actuel d'une action via Yahoo Finance

        Args:
            symbol: Symbole de l'action (ex: 'AAPL', 'MSFT')

        Returns:
            Prix actuel en EUR ou None si erreur
        """
        # Vérifier le cache
        if self._is_cache_valid(f"stock_{symbol}"):
            return self.cache[f"stock_{symbol}"]["price"]

        try:
            # Mapping des symboles vers les symboles Yahoo Finance corrects
            symbol_mapping = {
                "HIWS": "HIWS.PA",  # Euronext Paris
                # Ajouter d'autres mappings si nécessaire
            }

            yahoo_symbol = symbol_mapping.get(symbol, symbol)
            ticker = yf.Ticker(yahoo_symbol)

            # Récupérer les données des 2 derniers jours pour avoir le prix le plus récent
            hist = ticker.history(period="2d")

            if not hist.empty:
                # Prendre le dernier prix de clôture disponible
                price = float(hist["Close"].iloc[-1])

                # Mettre en cache
                self.cache[f"stock_{symbol}"] = {"price": price, "timestamp": time.time()}

                return price

            return None

        except ValueError as e:
            print(f"Erreur de données pour l'action {symbol}: {e}")
            return None
        except Exception as e:
            print(f"Erreur inattendue lors de la récupération du prix de l'action {symbol}: {e}")
            return None

    def get_current_price(self, symbol: str, asset_type: str) -> Optional[float]:
        """
        Récupère le prix actuel d'un actif selon son type

        Args:
            symbol: Symbole de l'actif
            asset_type: Type d'actif ('crypto' ou 'bourse')

        Returns:
            Prix actuel en EUR ou None si erreur
        """
        if asset_type.lower() == "crypto":
            return self.get_crypto_price(symbol)
        elif asset_type.lower() == "bourse":
            return self.get_stock_price(symbol)
        else:
            return None

    def calculate_investment_performance(
        self, investments: List[Dict], asset_type: str
    ) -> List[Dict]:
        """
        Calcule la performance de chaque investissement

        Args:
            investments: Liste des investissements
            asset_type: Type d'actif ('crypto' ou 'bourse')

        Returns:
            Liste des investissements avec données de performance
        """
        enriched_investments = []

        for investment in investments:
            enriched_investment = investment.copy()

            symbol = investment["symbole"]
            current_price = self.get_current_price(symbol, asset_type)

            if current_price is not None:
                buy_price = investment["prix_unitaire"]
                quantity = investment["quantite"]
                initial_value = investment["montant"]

                # Valeur actuelle du portefeuille
                current_value = quantity * current_price

                # Plus-value/moins-value en valeur absolue
                pnl_amount = current_value - initial_value

                # Plus-value/moins-value en pourcentage
                pnl_percentage = ((current_price - buy_price) / buy_price) * 100

                enriched_investment.update(
                    {
                        "prix_actuel": current_price,
                        "valeur_actuelle": current_value,
                        "pnl_montant": pnl_amount,
                        "pnl_pourcentage": pnl_percentage,
                        "prix_recupere": True,
                    }
                )
            else:
                enriched_investment.update(
                    {
                        "prix_actuel": None,
                        "valeur_actuelle": investment["montant"],
                        "pnl_montant": 0,
                        "pnl_pourcentage": 0,
                        "prix_recupere": False,
                    }
                )

            enriched_investments.append(enriched_investment)

        return enriched_investments

    def calculate_portfolio_summary(
        self, crypto_investments: List[Dict], stock_investments: List[Dict]
    ) -> Dict:
        """
        Calcule un résumé des performances du portfolio complet

        Args:
            crypto_investments: Investissements crypto avec performances
            stock_investments: Investissements bourse avec performances

        Returns:
            Dictionnaire avec les métriques du portfolio
        """
        # Calculs pour crypto
        crypto_initial = sum([inv["montant"] for inv in crypto_investments])
        crypto_current = sum([inv["valeur_actuelle"] for inv in crypto_investments])
        crypto_pnl = crypto_current - crypto_initial

        # Calculs pour bourse
        stock_initial = sum([inv["montant"] for inv in stock_investments])
        stock_current = sum([inv["valeur_actuelle"] for inv in stock_investments])
        stock_pnl = stock_current - stock_initial

        # Totaux
        total_initial = crypto_initial + stock_initial
        total_current = crypto_current + stock_current
        total_pnl = total_current - total_initial

        # Pourcentages
        crypto_pnl_pct = (crypto_pnl / crypto_initial * 100) if crypto_initial > 0 else 0
        stock_pnl_pct = (stock_pnl / stock_initial * 100) if stock_initial > 0 else 0
        total_pnl_pct = (total_pnl / total_initial * 100) if total_initial > 0 else 0

        return {
            "crypto": {
                "valeur_initiale": crypto_initial,
                "valeur_actuelle": crypto_current,
                "pnl_montant": crypto_pnl,
                "pnl_pourcentage": crypto_pnl_pct,
            },
            "bourse": {
                "valeur_initiale": stock_initial,
                "valeur_actuelle": stock_current,
                "pnl_montant": stock_pnl,
                "pnl_pourcentage": stock_pnl_pct,
            },
            "total": {
                "valeur_initiale": total_initial,
                "valeur_actuelle": total_current,
                "pnl_montant": total_pnl,
                "pnl_pourcentage": total_pnl_pct,
            },
        }

    def clear_cache(self):
        """Vide le cache des prix"""
        self.cache.clear()
