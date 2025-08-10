"""
Service pour récupérer les prix en temps réel et calculer les performances
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

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

    def get_crypto_price(self, symbol: str, show_log: bool = True) -> Optional[float]:
        """
        Récupère le prix actuel d'une crypto via Yahoo Finance

        Args:
            symbol: Symbole de la crypto (ex: 'BTC', 'ETH')
            show_log: Afficher ou non les logs (par défaut True)

        Returns:
            Prix actuel en EUR ou None si erreur
        """
        # Vérifier le cache
        if self._is_cache_valid(f"crypto_{symbol}"):
            return self.cache[f"crypto_{symbol}"]["price"]

        try:
            # Vérifier les mappings appris depuis Supabase
            learned_symbol = self._get_learned_mapping(symbol)
            if learned_symbol:
                ticker = yf.Ticker(learned_symbol)
                hist = ticker.history(period="2d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    # Mettre en cache
                    self.cache[f"crypto_{symbol}"] = {"price": price, "timestamp": time.time()}
                    if show_log:
                        print(
                            f"Mapping crypto trouvé:"
                            f" {symbol} -> {learned_symbol} (prix: {price:.2f}€)"
                        )
                    return price

            if show_log:
                print(f"❌ Aucun mapping trouvé pour la crypto: {symbol}")
            return None

        except Exception as e:
            if show_log:
                print(f"Erreur lors de la récupération du prix crypto de {symbol}: {e}")
            return None

    def _try_multiple_symbols(
            self, base_symbol: str, show_log: bool = True
    ) -> Optional[Tuple[str, float]]:
        """
        Essaie plusieurs variantes d'un symbole pour trouver le bon

        Args:
            base_symbol: Symbole de base à tester
            show_log: Afficher ou non les logs (par défaut True)

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
                    if show_log:
                        print(
                            f"Symbole bourse trouvé:"
                            f" {base_symbol} -> {variant} (prix: {price:.2f}€)"
                        )
                    return variant, price

            except Exception:
                continue

        return None

    def get_stock_price(self, symbol: str, show_log: bool = True) -> Optional[float]:
        """
        Récupère le prix actuel d'une action via Yahoo Finance avec recherche automatique

        Args:
            symbol: Symbole de l'action (ex: 'AAPL', 'NVIDIA', 'HIWS')
            show_log: Afficher ou non les logs (par défaut True)

        Returns:
            Prix actuel en EUR ou None si erreur
        """
        # Vérifier le cache
        if self._is_cache_valid(f"stock_{symbol}"):
            return self.cache[f"stock_{symbol}"]["price"]

        try:
            # Essayer le symbole tel quel puis les variantes
            result = self._try_multiple_symbols(symbol.upper(), show_log)

            if result:
                found_symbol, price = result
                # Mettre en cache
                self.cache[f"stock_{symbol}"] = {"price": price, "timestamp": time.time()}
                return price

            if show_log:
                print(f"❌ Aucun symbole trouvé pour: {symbol}")
            return None

        except Exception as e:
            if show_log:
                print(
                    f"Erreur inattendue lors de la récupération du prix de l'action {symbol}: {e}"
                )
            return None

    def get_current_price(
            self, symbol: str, asset_type: str, show_log: bool = True
    ) -> Optional[float]:
        """
        Récupère le prix actuel d'un actif selon son type

        Args:
            symbol: Symbole de l'actif
            asset_type: Type d'actif ('crypto' ou 'bourse')
            show_log: Afficher ou non les logs (par défaut True)

        Returns:
            Prix actuel en EUR ou None si erreur
        """
        if asset_type.lower() == "crypto":
            return self.get_crypto_price(symbol, show_log)
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
                        if show_log:
                            print(
                                f"Mapping bourse trouvé:"
                                f" {symbol} -> {learned_symbol} (prix: {price:.2f}€)"
                            )
                        return price
                except Exception:
                    pass

            # Sinon, utiliser la méthode normale
            return self.get_stock_price(symbol, show_log)
        else:
            return None

    def calculate_investment_performance(
            self, investments: List[Dict], asset_type: str
    ) -> List[Dict]:
        """
        Calcule la performance de chaque investissement (achats ET ventes)

        Args:
            investments: Liste des investissements (achats et ventes)
            asset_type: Type d'actif ('crypto' ou 'bourse')

        Returns:
            Liste des investissements avec données de performance
        """
        enriched_investments = []

        # Récupérer les symboles uniques pour éviter les appels API redondants
        unique_symbols = list(set([inv["symbole"] for inv in investments]))

        # Récupérer les prix une seule fois par symbole
        symbol_prices = {}
        for symbol in unique_symbols:
            symbol_prices[symbol] = self.get_current_price(symbol, asset_type, show_log=True)

        for investment in investments:
            enriched_investment = investment.copy()

            symbol = investment["symbole"]
            current_price = symbol_prices[symbol]
            is_sale = investment.get("type_operation") == "Vente"

            if current_price is not None:
                transaction_price = investment["prix_unitaire"]
                quantity = investment["quantite"]
                initial_value = investment["montant"]

                if is_sale:
                    # Pour les ventes : valeur actuelle = 0 (on n'a plus l'actif)
                    # PnL = prix de vente vs prix d'achat moyen (calculé plus tard via FIFO)
                    current_value = 0.0

                    # PnL temporaire basé sur le prix actuel vs prix de vente
                    # (Le PnL réalisé final sera calculé via FIFO dans calculate_realized_pnl)
                    pnl_amount = 0.0  # Sera calculé plus tard
                    pnl_percentage = 0.0  # Sera calculé plus tard

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
                    # Pour les achats : calcul normal (comme avant)
                    current_value = quantity * current_price

                    # Plus-value/moins-value en valeur absolue
                    pnl_amount = current_value - initial_value

                    # Plus-value/moins-value en pourcentage
                    pnl_percentage = ((current_price - transaction_price) / transaction_price) * 100

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
                # Prix non récupéré
                if is_sale:
                    current_value = 0.0
                else:
                    current_value = investment["montant"]

                enriched_investment.update(
                    {
                        "prix_actuel": None,
                        "valeur_actuelle": current_value,
                        "pnl_montant": 0,
                        "pnl_pourcentage": 0,
                        "prix_recupere": False,
                    }
                )

            enriched_investments.append(enriched_investment)

        return enriched_investments

    def calculate_realized_pnl(self, investments: List[Dict], symbol: str) -> Dict:
        """
        Calcule le PnL réalisé pour un symbole donné en utilisant la méthode FIFO

        Args:
            investments: Liste de tous les investissements pour ce symbole
            symbol: Symbole de l'actif

        Returns:
            Dict avec les informations de PnL réalisé
        """
        # Filtrer et trier par date (FIFO = First In, First Out)
        symbol_investments = [
            inv for inv in investments if inv["symbole"].upper() == symbol.upper()
        ]

        # Trier par date pour FIFO
        symbol_investments.sort(key=lambda x: x["date"])

        # Séparer achats et ventes
        purchases = [inv for inv in symbol_investments if inv.get("type_operation") != "Vente"]
        sales = [inv for inv in symbol_investments if inv.get("type_operation") == "Vente"]

        if not sales:
            return {
                "pnl_realise_montant": 0.0,
                "pnl_realise_pourcentage": 0.0,
                "quantite_vendue_totale": 0.0,
                "prix_moyen_vente": 0.0,
                "prix_moyen_achat_vendu": 0.0,
            }

        # Calcul FIFO
        import copy

        remaining_purchases = copy.deepcopy(purchases)  # Queue des achats restants
        total_pnl_realized = 0.0
        total_quantity_sold = 0.0
        total_sale_value = 0.0
        total_cost_basis = 0.0

        for sale in sales:
            sale_quantity = sale["quantite"]
            sale_price = sale["prix_unitaire"]
            quantity_to_match = sale_quantity

            total_quantity_sold += sale_quantity
            total_sale_value += sale["montant"]

            # Associer cette vente aux achats FIFO
            while quantity_to_match > 0 and remaining_purchases:
                purchase = remaining_purchases[0]
                available_qty = purchase["quantite"]
                purchase_price = purchase["prix_unitaire"]

                if available_qty <= quantity_to_match:
                    # Consommer tout cet achat
                    matched_qty = available_qty
                    remaining_purchases.pop(0)  # Retirer cet achat
                else:
                    # Consommer partiellement cet achat
                    matched_qty = quantity_to_match
                    purchase["quantite"] -= matched_qty  # Réduire la quantité restante

                # Calculer le PnL pour cette portion
                cost_basis = matched_qty * purchase_price
                sale_value = matched_qty * sale_price
                portion_pnl = sale_value - cost_basis

                total_pnl_realized += portion_pnl
                total_cost_basis += cost_basis
                quantity_to_match -= matched_qty

        # Calculs finaux
        avg_sale_price = total_sale_value / total_quantity_sold if total_quantity_sold > 0 else 0.0
        avg_purchase_price = (
            total_cost_basis / total_quantity_sold if total_quantity_sold > 0 else 0.0
        )
        pnl_percentage = (
            (total_pnl_realized / total_cost_basis * 100) if total_cost_basis > 0 else 0.0
        )

        return {
            "pnl_realise_montant": total_pnl_realized,
            "pnl_realise_pourcentage": pnl_percentage,
            "quantite_vendue_totale": total_quantity_sold,
            "prix_moyen_vente": avg_sale_price,
            "prix_moyen_achat_vendu": avg_purchase_price,
        }

    def calculate_portfolio_summary(
            self, crypto_investments: List[Dict], stock_investments: List[Dict]
    ) -> Dict:
        """
        Calcule un résumé des performances du portfolio complet (avec PnL réalisé/non réalisé)

        Args:
            crypto_investments: Investissements crypto avec performances
            stock_investments: Investissements bourse avec performances

        Returns:
            Dictionnaire avec les métriques du portfolio (incluant PnL réalisé)
        """

        # Fonction helper pour calculer les métriques d'un type d'actif
        def calculate_asset_metrics(investments, asset_type_name):
            if not investments:
                return {
                    "valeur_initiale": 0,
                    "valeur_actuelle": 0,
                    "pnl_montant": 0,
                    "pnl_pourcentage": 0,
                    "pnl_realise": 0,
                    "pnl_non_realise": 0,
                }

            # Séparer achats et ventes pour calculs corrects
            purchases = [inv for inv in investments if inv.get("type_operation") != "Vente"]

            # Valeur initiale = somme des achats seulement
            initial_value = sum([inv["montant"] for inv in purchases])

            # Valeur actuelle = somme des valeurs actuelles (achats seulement, ventes = 0)
            current_value = sum([inv["valeur_actuelle"] for inv in purchases])

            # PnL non réalisé = différence valeur actuelle vs investissement initial
            unrealized_pnl = current_value - initial_value

            # PnL réalisé = calculer pour tous les symboles uniques
            unique_symbols = list(set([inv["symbole"] for inv in investments]))
            realized_pnl_total = 0.0

            for symbol in unique_symbols:
                realized_data = self.calculate_realized_pnl(investments, symbol)
                realized_pnl_total += realized_data["pnl_realise_montant"]

            # PnL total = réalisé + non réalisé
            total_pnl = realized_pnl_total + unrealized_pnl

            # Pourcentage basé sur la valeur initiale
            pnl_pct = (total_pnl / initial_value * 100) if initial_value > 0 else 0

            return {
                "valeur_initiale": initial_value,
                "valeur_actuelle": current_value,
                "pnl_montant": total_pnl,
                "pnl_pourcentage": pnl_pct,
                "pnl_realise": realized_pnl_total,
                "pnl_non_realise": unrealized_pnl,
            }

        # Calculs pour crypto et bourse
        crypto_metrics = calculate_asset_metrics(crypto_investments, "crypto")
        stock_metrics = calculate_asset_metrics(stock_investments, "bourse")

        # Totaux
        total_initial = crypto_metrics["valeur_initiale"] + stock_metrics["valeur_initiale"]
        total_current = crypto_metrics["valeur_actuelle"] + stock_metrics["valeur_actuelle"]
        total_realized = crypto_metrics["pnl_realise"] + stock_metrics["pnl_realise"]
        total_unrealized = crypto_metrics["pnl_non_realise"] + stock_metrics["pnl_non_realise"]
        total_pnl = total_realized + total_unrealized
        total_pnl_pct = (total_pnl / total_initial * 100) if total_initial > 0 else 0

        return {
            "crypto": crypto_metrics,
            "bourse": stock_metrics,
            "total": {
                "valeur_initiale": total_initial,
                "valeur_actuelle": total_current,
                "pnl_montant": total_pnl,
                "pnl_pourcentage": total_pnl_pct,
                "pnl_realise": total_realized,
                "pnl_non_realise": total_unrealized,
            },
        }

    def _get_learned_mapping(self, symbol: str) -> Optional[str]:
        """Récupère un mapping appris depuis Supabase"""
        if not self.supabase:
            return None

        try:
            result = (
                self.supabase.table("symbol_mappings")
                .select("yahoo_symbol")
                .eq("user_symbol", symbol.upper())
                .execute()
            )
            if result.data:
                return result.data[0]["yahoo_symbol"]
        except Exception as e:
            print(f"Erreur lors de la récupération du mapping pour {symbol}: {e}")
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
                        print(f"Mapping trouvé: {symbol} -> {learned_symbol} (prix: {price:.2f}€)")
                        return price, None
                except Exception:
                    print(f"❌ Erreur avec le mapping {symbol} -> {learned_symbol}")

            # 2. Pas de mapping trouvé
            return None, None

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
