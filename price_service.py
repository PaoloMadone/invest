"""
Service pour récupérer les prix en temps réel et calculer les performances
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
import yfinance as yf


class PriceService:
    """Service pour récupérer les prix des actifs et calculer les performances"""

    def __init__(self, supabase_client=None):
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
        self.supabase = supabase_client  # Client Supabase pour persistance

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

    def _try_multiple_symbols(self, base_symbol: str) -> Optional[Tuple[str, float]]:
        """
        Essaie plusieurs variantes d'un symbole pour trouver le bon

        Args:
            base_symbol: Symbole de base à tester

        Returns:
            Tuple (symbole trouvé, prix) ou None si aucun ne fonctionne
        """
        # Liste des suffixes à essayer pour les marchés européens et américains
        variants = [
            base_symbol,  # Symbole tel quel
            f"{base_symbol}.PA",  # Euronext Paris
            f"{base_symbol}.L",  # London Stock Exchange
            f"{base_symbol}.F",  # Frankfurt
            f"{base_symbol}.MI",  # Milano
            f"{base_symbol}.MC",  # Madrid
            f"{base_symbol}.AS",  # Amsterdam
        ]

        for variant in variants:
            try:
                ticker = yf.Ticker(variant)
                hist = ticker.history(period="2d")

                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    print(f"✅ Symbole trouvé: {base_symbol} -> {variant} (prix: {price:.2f})")
                    return variant, price

            except Exception:
                continue

        return None

    def get_stock_price(self, symbol: str) -> Optional[float]:
        """
        Récupère le prix actuel d'une action via Yahoo Finance avec recherche automatique

        Args:
            symbol: Symbole de l'action (ex: 'AAPL', 'NVIDIA', 'HIWS')

        Returns:
            Prix actuel en EUR ou None si erreur
        """
        # Vérifier le cache
        if self._is_cache_valid(f"stock_{symbol}"):
            return self.cache[f"stock_{symbol}"]["price"]

        try:
            # Essayer le symbole tel quel puis les variantes
            result = self._try_multiple_symbols(symbol.upper())

            if result:
                found_symbol, price = result
                # Mettre en cache
                self.cache[f"stock_{symbol}"] = {"price": price, "timestamp": time.time()}
                return price

            print(f"❌ Aucun symbole trouvé pour: {symbol}")
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
            # Vérifier d'abord le mapping pour les symboles existants
            learned_symbol = self._get_learned_mapping(symbol)
            if learned_symbol:
                try:
                    ticker = yf.Ticker(learned_symbol)
                    hist = ticker.history(period="2d")
                    if not hist.empty:
                        price = float(hist["Close"].iloc[-1])
                        # Mettre en cache
                        self.cache[f"stock_{symbol}"] = {"price": price, "timestamp": time.time()}
                        return price
                except Exception:
                    pass

            # Sinon, utiliser la méthode normale
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

    def _get_learned_mapping(self, symbol: str) -> Optional[str]:
        """Récupère un mapping appris depuis Supabase"""
        import streamlit as st

        if not self.supabase:
            st.write(f"🔍 Pas de client Supabase pour {symbol}")
            return None

        try:
            st.write(f"🔍 Recherche mapping pour: {symbol.upper()}")
            result = (
                self.supabase.table("symbol_mappings")
                .select("yahoo_symbol")
                .eq("user_symbol", symbol.upper())
                .execute()
            )
            if result.data:
                yahoo_symbol = result.data[0]["yahoo_symbol"]
                st.write(f"✅ Mapping trouvé: {symbol.upper()} -> {yahoo_symbol}")
                return yahoo_symbol
            else:
                st.write(f"❌ Aucun mapping trouvé pour: {symbol.upper()}")
        except Exception as e:
            st.error(f"Erreur lors de la récupération du mapping pour {symbol}: {e}")
        return None

    def _save_learned_mapping(self, user_symbol: str, yahoo_symbol: str, company_name: str = None):
        """Sauvegarde un mapping appris dans Supabase"""
        if not self.supabase:
            return

        try:
            self.supabase.table("symbol_mappings").upsert(
                {
                    "user_symbol": user_symbol.upper(),
                    "yahoo_symbol": yahoo_symbol,
                    "company_name": company_name,
                    "created_at": datetime.now().isoformat(),
                }
            ).execute()
            print(f"💾 Mapping sauvegardé: {user_symbol} -> {yahoo_symbol}")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du mapping: {e}")

    def _find_multiple_variants(self, base_symbol: str) -> List[Tuple[str, float, str]]:
        """
        Trouve toutes les variantes valides d'un symbole

        Returns:
            Liste de tuples (symbole, prix, nom_marché)
        """
        variants_info = [
            (base_symbol, "NASDAQ/NYSE"),
            (f"{base_symbol}.F", "Frankfurt (XETRA)"),
            (f"{base_symbol}.DE", "Deutsche Börse"),
            (f"{base_symbol}.PA", "Euronext Paris"),
            (f"{base_symbol}.L", "London Stock Exchange"),
            (f"{base_symbol}.MI", "Milano"),
            (f"{base_symbol}.MC", "Madrid"),
            (f"{base_symbol}.AS", "Amsterdam"),
            (f"{base_symbol}.BR", "Brussels"),
            (f"{base_symbol}.SW", "Switzerland"),
        ]

        found_variants = []

        for variant, market_name in variants_info:
            try:
                ticker = yf.Ticker(variant)
                hist = ticker.history(period="2d")

                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    # Essayer de récupérer le nom de l'entreprise
                    try:
                        info = ticker.info
                        company_name = info.get("longName", info.get("shortName", variant))
                    except Exception:
                        company_name = variant

                    found_variants.append((variant, price, market_name, company_name))

            except Exception:
                continue

        return found_variants

    def get_stock_price_with_choice(self, symbol: str) -> Tuple[Optional[float], Optional[List]]:
        """
        Récupère le prix d'une action avec possibilité de choix multiple

        Returns:
            Tuple (prix, liste_choix) où liste_choix est None si un seul résultat
        """
        # Vérifier le cache
        if self._is_cache_valid(f"stock_{symbol}"):
            return self.cache[f"stock_{symbol}"]["price"], None

        try:
            # 1. Vérifier les mappings appris
            learned_symbol = self._get_learned_mapping(symbol)
            if learned_symbol:
                try:
                    ticker = yf.Ticker(learned_symbol)
                    hist = ticker.history(period="2d")
                    if not hist.empty:
                        price = float(hist["Close"].iloc[-1])
                        self.cache[f"stock_{symbol}"] = {"price": price, "timestamp": time.time()}
                        print(
                            f"✅ Mapping trouvé: {symbol} -> {learned_symbol} (prix: {price:.2f}€)"
                        )
                        return price, None
                except Exception:
                    print(f"❌ Erreur avec le mapping {symbol} -> {learned_symbol}")

            # 2. Rechercher toutes les variantes
            variants = self._find_multiple_variants(symbol.upper())

            if len(variants) == 0:
                return None, None
            elif len(variants) == 1:
                # Un seul résultat trouvé, l'utiliser directement
                variant, price, market, company = variants[0]
                self.cache[f"stock_{symbol}"] = {"price": price, "timestamp": time.time()}
                # Sauvegarder automatiquement si c'est différent du symbole original
                if variant != symbol.upper():
                    self._save_learned_mapping(symbol, variant, company)
                return price, None
            else:
                # Plusieurs résultats, retourner pour que l'utilisateur choisisse
                return None, variants

        except Exception as e:
            print(f"Erreur lors de la récupération du prix de {symbol}: {e}")
            return None, None

    def save_user_choice(
        self, user_symbol: str, chosen_yahoo_symbol: str, company_name: str = None
    ) -> Optional[float]:
        """
        Sauvegarde le choix de l'utilisateur et retourne le prix
        """
        self._save_learned_mapping(user_symbol, chosen_yahoo_symbol, company_name)

        # Récupérer le prix du symbole choisi
        try:
            ticker = yf.Ticker(chosen_yahoo_symbol)
            hist = ticker.history(period="2d")

            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                self.cache[f"stock_{user_symbol}"] = {"price": price, "timestamp": time.time()}
                return price
        except Exception as e:
            print(f"Erreur lors de la récupération du prix pour {chosen_yahoo_symbol}: {e}")

        return None

    def clear_cache(self):
        """Vide le cache des prix"""
        self.cache.clear()
