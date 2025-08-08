import copy
import json
import math
import os
from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

import business_logic
from price_service import PriceService

# Charger les variables d'environnement
load_dotenv()

st.set_page_config(page_title="Tracker d'Investissements", page_icon="📈", layout="wide")

# Configuration Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DATA_FILE = "investments_data.json"


def load_data():
    try:
        # Charger depuis Supabase
        revenus = supabase.table("revenus").select("*").execute().data
        bourse = supabase.table("bourse").select("*").execute().data
        crypto = supabase.table("crypto").select("*").execute().data

        return {"revenus": revenus, "bourse": bourse, "crypto": crypto}
    except Exception as e:
        st.error(f"Erreur lors du chargement des données: {e}")
        return {"revenus": [], "bourse": [], "crypto": []}


def get_existing_symbols(data, asset_type):
    """Récupère les symboles uniques existants pour un type d'actif"""
    if asset_type == "bourse":
        symbols = [inv["symbole"] for inv in data["bourse"]]
    elif asset_type == "crypto":
        symbols = [inv["symbole"] for inv in data["crypto"]]
    else:
        symbols = []

    return sorted(list(set(symbols)))


def save_data(data):
    # Sauvegarder aussi en local pour backup (optionnel)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def main():
    st.title("Tracker d'Investissements")
    st.markdown("---")

    data = load_data()

    # Initialiser le service de prix
    if "price_service" not in st.session_state:
        st.session_state.price_service = PriceService(supabase)

    # Sidebar pour saisie des revenus
    with st.sidebar:
        st.header("Saisie des Revenus")

        revenu_net = st.number_input(
            "Revenu net mensuel (€)",
            min_value=0,
            value=0,
            step=100,
            help="Saisissez votre revenu net mensuel",
        )

        col_mois, col_annee = st.columns(2)
        with col_mois:
            mois_revenu = st.selectbox(
                "Mois",
                options=list(range(1, 13)),
                format_func=lambda x: [
                    "Janvier",
                    "Février",
                    "Mars",
                    "Avril",
                    "Mai",
                    "Juin",
                    "Juillet",
                    "Août",
                    "Septembre",
                    "Octobre",
                    "Novembre",
                    "Décembre",
                ][x - 1],
                index=date.today().month - 1,
            )
        with col_annee:
            annee_revenu = st.number_input(
                "Année", min_value=2020, max_value=2030, value=date.today().year, step=1
            )

        if st.button("Enregistrer Revenu"):
            if revenu_net > 0:
                periode_actuelle = f"{annee_revenu}-{mois_revenu:02d}"

                # Vérifier si le revenu pour cette période existe déjà
                periode_existante = any(r["periode"] == periode_actuelle for r in data["revenus"])

                if periode_existante:
                    st.error(f"Un revenu pour {periode_actuelle} existe déjà!")
                else:
                    montant_investissement_bourse = round(revenu_net * 0.10, 2)
                    montant_investissement_crypto = round(revenu_net * 0.10, 2)
                    # Ajouter à Supabase
                    try:
                        supabase.table("revenus").insert(
                            {
                                "mois": mois_revenu,
                                "annee": int(annee_revenu),
                                "periode": periode_actuelle,
                                "montant": revenu_net,
                                "investissement_disponible_bourse": montant_investissement_bourse,
                                "investissement_disponible_crypto": montant_investissement_crypto,
                            }
                        ).execute()

                        # Recharger les données
                        data = load_data()
                        save_data(data)
                    except Exception as e:
                        st.error(f"Erreur lors de l'ajout du revenu: {e}")
                        return
                    st.success(
                        f"Revenu enregistré! {montant_investissement_bourse:,.2f}€ pour bourse, "
                        f"{montant_investissement_crypto:,.2f}€ pour crypto".replace(",", " ")
                    )
                    st.rerun()

    # Calcul des budgets d'investissement séparés
    budget_bourse_brut = sum([r["investissement_disponible_bourse"] for r in data["revenus"]])
    budget_crypto_brut = sum([r["investissement_disponible_crypto"] for r in data["revenus"]])
    budget_bourse = math.ceil(budget_bourse_brut)
    budget_crypto = math.ceil(budget_crypto_brut)
    budget_total = budget_bourse + budget_crypto

    budget_utilise_bourse = sum(
        [b["montant"] for b in data["bourse"] if not b.get("hors_budget", False)]
    )
    budget_utilise_crypto = sum(
        [c["montant"] for c in data["crypto"] if not c.get("hors_budget", False)]
    )

    # Total réellement investi (incluant hors budget)
    total_investi_bourse = sum([b["montant"] for b in data["bourse"]])
    total_investi_crypto = sum([c["montant"] for c in data["crypto"]])

    budget_restant_bourse = budget_bourse - budget_utilise_bourse
    budget_restant_crypto = budget_crypto - budget_utilise_crypto

    # Métriques globales avec performances en temps réel
    total_investi_reel = total_investi_bourse + total_investi_crypto
    total_restant = budget_restant_bourse + budget_restant_crypto

    # Calculer les performances globales au chargement si nécessaire
    portfolio_summary = st.session_state.get("portfolio_summary")

    # Ne calculer que si on n'a pas de résumé ET qu'on n'est pas en train de gérer des choix de symboles
    should_calculate_performance = (
        not portfolio_summary
        and (data["bourse"] or data["crypto"])
        and not hasattr(st.session_state, "symbol_choices")
        and not hasattr(st.session_state, "pending_symbol")
    )

    if should_calculate_performance:
        # Calculer sans spinner pour éviter les rerun intempestifs
        crypto_with_perf = (
            st.session_state.price_service.calculate_investment_performance(
                data["crypto"], "crypto"
            )
            if data["crypto"]
            else []
        )

        bourse_with_perf = (
            st.session_state.price_service.calculate_investment_performance(
                data["bourse"], "bourse"
            )
            if data["bourse"]
            else []
        )

        portfolio_summary = st.session_state.price_service.calculate_portfolio_summary(
            crypto_with_perf, bourse_with_perf
        )

        # Mettre en cache dans la session
        st.session_state.portfolio_summary = portfolio_summary

        # Mettre aussi en cache les données individuelles pour les onglets
        if bourse_with_perf:
            bourse_cache_key = f"bourse_perf_{len(data['bourse'])}"
            st.session_state[bourse_cache_key] = bourse_with_perf
        if crypto_with_perf:
            crypto_cache_key = f"crypto_perf_{len(data['crypto'])}"
            st.session_state[crypto_cache_key] = crypto_with_perf

    # Bouton pour actualiser les prix - affiché seulement après le calcul des performances OU s'il n'y a pas d'investissements
    if portfolio_summary or not (data["bourse"] or data["crypto"]):
        col_refresh, col_empty = st.columns([1, 5])
        with col_refresh:
            if st.button("🔄 Actualiser les prix"):
                st.session_state.price_service.clear_cache()
                # Vider aussi le cache des performances
                if "portfolio_summary" in st.session_state:
                    del st.session_state.portfolio_summary
                if "bourse_data_processed" in st.session_state:
                    del st.session_state.bourse_data_processed
                if "crypto_data_processed" in st.session_state:
                    del st.session_state.crypto_data_processed
                # Vider les caches des onglets individuels
                for key in list(st.session_state.keys()):
                    if key.startswith("bourse_perf_") or key.startswith("crypto_perf_"):
                        del st.session_state[key]
                st.rerun()

    # Tabs pour Bourse et Crypto
    tab_revenus, tab_bourse, tab_crypto, tab_overview = st.tabs(
        ["Revenus", "Bourse", "Crypto", "Vue d'ensemble"]
    )

    with tab_bourse:
        st.header("Investissements Bourse")

        # Métriques spécifiques bourse
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
        with col_m1:
            st.metric("Budget Bourse", f"{budget_bourse:,}€".replace(",", " "))
        with col_m2:
            st.metric("Investi Bourse", f"{total_investi_bourse:,.2f}€".replace(",", " "))
        with col_m3:
            st.metric("Restant Bourse", f"{budget_restant_bourse:,.2f}€".replace(",", " "))
        with col_m4:
            # Calculer la valeur actuelle à partir des données individuelles si disponibles
            bourse_cache_key = f"bourse_perf_{len(data['bourse'])}"
            bourse_with_perf = st.session_state.get(bourse_cache_key)

            if bourse_with_perf and any(inv.get("valeur_actuelle") for inv in bourse_with_perf):
                valeur_actuelle_bourse = sum(
                    inv.get("valeur_actuelle", inv["montant"]) for inv in bourse_with_perf
                )
                st.metric("Valeur Actuelle", f"{valeur_actuelle_bourse:,.2f}€".replace(",", " "))
            elif portfolio_summary and portfolio_summary["bourse"]["valeur_actuelle"] > 0:
                valeur_actuelle_bourse = portfolio_summary["bourse"]["valeur_actuelle"]
                st.metric("Valeur Actuelle", f"{valeur_actuelle_bourse:,.2f}€".replace(",", " "))
            else:
                st.metric("Valeur Actuelle", f"{total_investi_bourse:,.2f}€".replace(",", " "))
        with col_m5:
            # Calculer le P&L à partir des données individuelles si disponibles
            if bourse_with_perf and any(
                inv.get("pnl_montant") is not None for inv in bourse_with_perf
            ):
                pnl_bourse = sum(
                    inv.get("pnl_montant", 0)
                    for inv in bourse_with_perf
                    if inv.get("pnl_montant") is not None
                )
                pnl_pct_bourse = (
                    (pnl_bourse / total_investi_bourse * 100) if total_investi_bourse > 0 else 0
                )
                st.metric(
                    "P&L Total",
                    f"{pnl_bourse:+,.2f}€".replace(",", " "),
                    delta=f"{pnl_pct_bourse:+.1f}%",
                )
            elif portfolio_summary and portfolio_summary["bourse"]["pnl_montant"] is not None:
                pnl_bourse = portfolio_summary["bourse"]["pnl_montant"]
                pnl_pct_bourse = portfolio_summary["bourse"]["pnl_pourcentage"]
                st.metric(
                    "P&L Total",
                    f"{pnl_bourse:+,.2f}€".replace(",", " "),
                    delta=f"{pnl_pct_bourse:+.1f}%",
                )
            else:
                st.metric("P&L Total", "0€", delta="0.0%")

        st.markdown("---")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Nouvel investissement")

            # Saisie du symbole avec liste déroulante
            existing_symbols_bourse = get_existing_symbols(data, "bourse")

            if existing_symbols_bourse:
                # Utiliser un selectbox avec les symboles existants + option "Autre"
                options = existing_symbols_bourse + ["🆕 Autre symbole..."]
                symbole_choice = st.selectbox(
                    "Symbole",
                    options=options,
                    index=None,
                    placeholder="-- Choisir un symbole --",
                    help="Choisissez un symbole existant ou 'Autre symbole...' "
                    "pour saisir manuellement",
                )

                if symbole_choice == "🆕 Autre symbole...":
                    symbole_bourse = st.text_input(
                        "",
                        placeholder="Ex: NVIDIA, AAPL, HIWS...",
                        help="Tapez le nom ou symbole de l'action",
                        label_visibility="collapsed",
                    )
                elif symbole_choice is not None:
                    symbole_bourse = symbole_choice
                else:
                    symbole_bourse = ""
            else:
                # Si aucun symbole existant, saisie directe
                symbole_bourse = st.text_input(
                    "Symbole",
                    placeholder="Ex: NVIDIA, AAPL, HIWS...",
                    help="Tapez le nom ou symbole de l'action",
                )

            hors_budget_bourse = st.checkbox(
                "Hors budget (conversion/existant)",
                help="Cochez si c'est un investissement existant "
                "ou une conversion qui ne doit pas être déduit du budget",
                key="bourse_hors_budget",
            )

            # Type d'opération
            type_operation_bourse = st.selectbox(
                "Type d'opération",
                options=["Achat", "Vente", "RoundUP", "SaveBack"],
                index=0,
                help="Sélectionnez le type d'opération (achat, vente, roundup, ou saveback)",
                key="bourse_type_operation",
            )

            montant_bourse = st.number_input(
                "Montant (€)",
                min_value=0.0,
                value=None,
                step=10.0,
                key="bourse_montant",
                help="Saisissez le montant de votre investissement",
            )
            date_bourse = st.date_input("Date d'achat", key="bourse_date")
            prix_unitaire_bourse = st.number_input(
                "Prix unitaire (€)", min_value=0.0, value=None, step=0.01, key="bourse_prix"
            )

            # Interface de choix si plusieurs options trouvées
            if hasattr(st.session_state, "symbol_choices") and st.session_state.symbol_choices:
                st.subheader(f"Choisir le symbole pour '{st.session_state.pending_symbol}':")

                choices = st.session_state.symbol_choices
                choice_labels = []

                for i, (variant, price, market, company) in enumerate(choices):
                    label = f"{variant} ({market}) - {company} - {price:.2f}€"
                    choice_labels.append(label)

                selected_choice = st.radio(
                    "Symboles trouvés:",
                    options=range(len(choices)),
                    format_func=lambda x: choice_labels[x],
                    key="symbol_choice_radio",
                )

                col_choose, col_cancel = st.columns(2)

                with col_choose:
                    if st.button("✅ Utiliser ce symbole", key="confirm_choice"):
                        chosen_variant, chosen_price, chosen_market, chosen_company = choices[
                            selected_choice
                        ]

                        # Sauvegarder le choix
                        final_price = st.session_state.price_service.save_user_choice(
                            st.session_state.pending_symbol, chosen_variant, chosen_company
                        )

                        if final_price:
                            st.success(
                                f"💾 Choix sauvegardé ! {st.session_state.pending_symbol} → "
                                f"{chosen_variant} ({final_price:.2f}€)"
                            )

                        # Nettoyer les variables de session
                        del st.session_state.symbol_choices
                        del st.session_state.pending_symbol
                        st.rerun()

                with col_cancel:
                    if st.button("❌ Annuler", key="cancel_choice"):
                        del st.session_state.symbol_choices
                        del st.session_state.pending_symbol
                        st.rerun()

            if st.button("Ajouter Investissement Bourse"):
                if symbole_bourse and (montant_bourse or 0) > 0 and (prix_unitaire_bourse or 0) > 0:

                    if type_operation_bourse == "Vente":
                        # Validation spécifique pour les ventes
                        quantite_vente = montant_bourse / prix_unitaire_bourse
                        erreurs = business_logic.valider_donnees_vente(
                            montant_bourse,
                            prix_unitaire_bourse,
                            symbole_bourse,
                            quantite_vente,
                            data["bourse"],
                        )

                        if erreurs:
                            for erreur in erreurs:
                                st.error(erreur)
                        else:
                            # Créer les données de vente
                            donnees_vente = business_logic.creer_donnees_vente(
                                date_bourse.isoformat(),
                                symbole_bourse,
                                montant_bourse,
                                prix_unitaire_bourse,
                            )

                            try:
                                supabase.table("bourse").insert(donnees_vente).execute()

                                # Recharger les données
                                data = load_data()
                                save_data(data)

                                # Vider tous les caches de performance qui pourraient être corrompus
                                keys_to_remove = [
                                    key
                                    for key in st.session_state.keys()
                                    if "perf" in key or "cache" in key
                                ]
                                for key in keys_to_remove:
                                    del st.session_state[key]

                                st.success("Vente bourse ajoutée!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur lors de l'ajout de la vente bourse: {e}")
                    else:
                        # Validation standard pour les achats
                        erreurs = business_logic.valider_donnees_investissement(
                            montant_bourse, prix_unitaire_bourse, symbole_bourse
                        )

                        if erreurs:
                            for erreur in erreurs:
                                st.error(erreur)
                        else:
                            # Créer les données d'investissement standard
                            donnees_investissement = business_logic.creer_donnees_investissement(
                                date_bourse.isoformat(),
                                symbole_bourse,
                                montant_bourse,
                                prix_unitaire_bourse,
                                hors_budget_bourse,
                            )
                            # Ajouter le type d'opération
                            donnees_investissement["type_operation"] = type_operation_bourse

                            try:
                                supabase.table("bourse").insert(donnees_investissement).execute()

                                # Recharger les données
                                data = load_data()
                                save_data(data)
                                st.success("Investissement bourse ajouté!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur lors de l'ajout de l'investissement bourse: {e}")

        with col2:
            if data["bourse"]:
                st.subheader("Portfolio Bourse")

                # Calculer les performances avec prix actuels seulement si nécessaire
                bourse_cache_key = f"bourse_perf_{len(data['bourse'])}"
                if bourse_cache_key not in st.session_state:
                    with st.spinner("Récupération des prix actuels..."):
                        bourse_with_perf = (
                            st.session_state.price_service.calculate_investment_performance(
                                data["bourse"], "bourse"
                            )
                        )
                        st.session_state[bourse_cache_key] = bourse_with_perf
                else:
                    bourse_with_perf = st.session_state[bourse_cache_key]

                if bourse_with_perf:
                    df_bourse = pd.DataFrame(bourse_with_perf)
                    # Trier par date AVANT la conversion en format d'affichage
                    df_bourse["date"] = pd.to_datetime(df_bourse["date"])
                    df_bourse = df_bourse.sort_values(
                        "date", ascending=False
                    )  # Plus récent en premier
                    df_bourse["date"] = df_bourse["date"].dt.strftime("%d/%m/%Y")

                    # Préparer les colonnes d'affichage
                    colonnes_base = ["date", "symbole", "quantite", "prix_unitaire", "montant"]

                    # Ajouter type_operation si disponible
                    if "type_operation" in df_bourse.columns:
                        colonnes_base.insert(2, "type_operation")

                    df_display = df_bourse[colonnes_base].copy()

                    # Formatage de base d'abord
                    df_display["montant"] = df_display["montant"].apply(
                        lambda x: f"{x:,.2f}€".replace(",", " ")
                    )
                    df_display["prix_unitaire"] = df_display["prix_unitaire"].apply(
                        lambda x: f"{x:,.2f}€".replace(",", " ")
                    )
                    df_display["quantite"] = df_display["quantite"].apply(lambda x: f"{x:.4f}")

                    # Ajouter les colonnes de performance si disponibles
                    styled_df = df_display  # Par défaut, pas de style
                    if (
                        "prix_actuel" in df_bourse.columns
                        and "pnl_montant" in df_bourse.columns
                        and "pnl_pourcentage" in df_bourse.columns
                    ):
                        df_display["prix_actuel"] = df_bourse["prix_actuel"].apply(
                            lambda x: f"{x:,.2f}€".replace(",", " ") if x is not None else "N/A"
                        )
                        df_display["valeur_actuelle"] = df_bourse["valeur_actuelle"].apply(
                            lambda x: f"{x:,.2f}€".replace(",", " ")
                        )
                        df_display["pnl_montant"] = df_bourse["pnl_montant"].apply(
                            lambda x: f"{x:+,.2f}€".replace(",", " ")
                        )
                        df_display["pnl_pourcentage"] = df_bourse["pnl_pourcentage"].apply(
                            lambda x: f"{x:+.1f}%"
                        )

                        # Renommer les colonnes d'abord
                        if "type_operation" in df_bourse.columns:
                            df_display.columns = [
                                "Date",
                                "Symbole",
                                "Type",
                                "Quantité",
                                "Prix Achat",
                                "Investi",
                                "Prix Actuel",
                                "Valeur Actuelle",
                                "P&L €",
                                "P&L %",
                            ]
                        else:
                            df_display.columns = [
                                "Date",
                                "Symbole",
                                "Quantité",
                                "Prix Achat",
                                "Investi",
                                "Prix Actuel",
                                "Valeur Actuelle",
                                "P&L €",
                                "P&L %",
                            ]

                        # Appliquer un style conditionnel pour les P&L
                        def color_pnl(val):
                            if "+" in str(val):
                                return "color: green"
                            elif "-" in str(val):
                                return "color: red"
                            return ""

                        # Appliquer le style maintenant que toutes les colonnes sont formatées
                        styled_df = df_display.style.map(color_pnl, subset=["P&L €", "P&L %"])
                        st.dataframe(styled_df, use_container_width=True)
                    else:
                        if "type_operation" in df_bourse.columns:
                            df_display.columns = [
                                "Date",
                                "Symbole",
                                "Type",
                                "Quantité",
                                "Prix Achat",
                                "Investi",
                            ]
                        else:
                            df_display.columns = [
                                "Date",
                                "Symbole",
                                "Quantité",
                                "Prix Achat",
                                "Investi",
                            ]
                        st.dataframe(df_display, use_container_width=True)
                        st.warning("Impossible de récupérer les prix actuels")

            else:
                st.info("Aucun investissement bourse enregistré")

        # Section Deep Dive - en dehors des colonnes pour être centrée
        if data["bourse"]:
            st.markdown("---")

            # Section Deep Dive
            st.subheader("📊 Deep Dive")

            # Récupérer les symboles uniques
            symboles_uniques = sorted(list(set([inv["symbole"] for inv in data["bourse"]])))

            # Récupérer la sélection précédente si elle existe
            default_index = None
            if "bourse_deep_dive_symbol" in st.session_state:
                previous_symbol = st.session_state.bourse_deep_dive_symbol
                if previous_symbol in symboles_uniques:
                    default_index = symboles_uniques.index(previous_symbol)

            symbole_selected = st.selectbox(
                "Sélectionner un titre pour analyse détaillée",
                options=symboles_uniques,
                index=default_index,
                placeholder="-- Choisir un titre --",
            )

            # Sauvegarder la sélection dans session_state
            if symbole_selected:
                st.session_state.bourse_deep_dive_symbol = symbole_selected

            if symbole_selected:
                # Récupérer les données de performance si disponibles
                bourse_cache_key = f"bourse_perf_{len(data['bourse'])}"
                bourse_with_perf = st.session_state.get(bourse_cache_key)

                # Filtrer les investissements pour ce symbole
                investissements_symbole = [
                    inv for inv in data["bourse"] if inv["symbole"] == symbole_selected
                ]

                if bourse_with_perf:
                    perf_symbole = [
                        inv for inv in bourse_with_perf if inv["symbole"] == symbole_selected
                    ]
                else:
                    perf_symbole = investissements_symbole

                # Calculer les statistiques
                # Quantité réelle disponible (achats - ventes)
                quantite_disponible = business_logic.calculer_quantite_disponible(
                    data["bourse"], symbole_selected
                )

                # Calculs séparés pour achats et ventes
                achats_symbole = [
                    inv for inv in investissements_symbole if inv.get("type_operation") != "Vente"
                ]
                ventes_symbole = [
                    inv for inv in investissements_symbole if inv.get("type_operation") == "Vente"
                ]

                # Total investi = somme des achats seulement (les ventes ne comptent pas comme investissement)
                total_investi_symbole = sum([inv["montant"] for inv in achats_symbole])

                # Prix moyen d'achat basé sur les achats seulement
                total_quantite_achats = sum([inv["quantite"] for inv in achats_symbole])
                prix_moyen_achat = (
                    total_investi_symbole / total_quantite_achats
                    if total_quantite_achats > 0
                    else 0
                )

                # PnL réalisé via FIFO
                pnl_realise_data = st.session_state.price_service.calculate_realized_pnl(
                    data["bourse"], symbole_selected
                )

                # Performance globale du titre
                if perf_symbole and any(inv.get("valeur_actuelle") for inv in perf_symbole):
                    valeur_actuelle_symbole = sum(
                        [inv.get("valeur_actuelle", inv["montant"]) for inv in perf_symbole]
                    )
                    pnl_symbole = valeur_actuelle_symbole - total_investi_symbole
                    pnl_pct_symbole = (
                        (pnl_symbole / total_investi_symbole * 100)
                        if total_investi_symbole > 0
                        else 0
                    )

                    # Première ligne : Métriques principales
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric(
                            "Total investi", f"{total_investi_symbole:,.2f}€".replace(",", " ")
                        )

                    with col2:
                        st.metric(
                            "Valeur actuelle", f"{valeur_actuelle_symbole:,.2f}€".replace(",", " ")
                        )

                    with col3:
                        st.metric("P&L %", "", delta=f"{pnl_pct_symbole:+.1f}%")

                    with col4:
                        st.metric("P&L €", "", delta=f"{pnl_symbole:+,.2f}€".replace(",", " "))

                # Deuxième ligne : Les métriques de détail
                col1, col2, col3 = st.columns(3)

                with col1:
                    if perf_symbole and any(inv.get("prix_actuel") for inv in perf_symbole):
                        prix_actuel = next(
                            (inv["prix_actuel"] for inv in perf_symbole if inv.get("prix_actuel")),
                            0,
                        )
                        st.metric("Prix actuel", f"{prix_actuel:,.2f}€".replace(",", " "))
                    else:
                        st.metric("Prix actuel", "N/A")

                with col2:
                    st.metric("Prix moyen d'achat", f"{prix_moyen_achat:,.2f}€".replace(",", " "))

                with col3:
                    st.metric("Quantité disponible", f"{quantite_disponible:.4f}")

                # Nouvelle ligne : Métriques de PnL réalisé/non réalisé
                if ventes_symbole:  # Afficher seulement s'il y a des ventes
                    st.markdown("#### 💰 Analyse PnL Réalisé vs Non Réalisé")

                    # Première ligne : PnL
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        pnl_realise = pnl_realise_data["pnl_realise_montant"]
                        st.metric("PnL Réalisé €", f"{pnl_realise:+,.2f}€".replace(",", " "))

                    with col2:
                        pnl_realise_pct = pnl_realise_data["pnl_realise_pourcentage"]
                        st.metric("PnL Réalisé %", f"{pnl_realise_pct:+.1f}%")

                    with col3:
                        # PnL non réalisé = PnL actuel - PnL réalisé
                        pnl_non_realise = (
                            pnl_symbole - pnl_realise if "pnl_symbole" in locals() else -pnl_realise
                        )
                        st.metric(
                            "PnL Non Réalisé €", f"{pnl_non_realise:+,.2f}€".replace(",", " ")
                        )

                    with col4:
                        quantite_vendue = pnl_realise_data["quantite_vendue_totale"]
                        st.metric("Quantité Vendue", f"{quantite_vendue:.4f}")

                    # Deuxième ligne : Prix moyens
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        prix_moyen_vente = pnl_realise_data["prix_moyen_vente"]
                        st.metric("Prix Moyen Vente", f"{prix_moyen_vente:,.2f}€".replace(",", " "))

                    with col2:
                        prix_moyen_achat_vendu = pnl_realise_data["prix_moyen_achat_vendu"]
                        st.metric(
                            "Prix Moyen Achat Vendu",
                            f"{prix_moyen_achat_vendu:,.2f}€".replace(",", " "),
                        )

                    with col3:
                        # Différence de prix
                        diff_prix = prix_moyen_vente - prix_moyen_achat_vendu
                        st.metric("Différence Prix", f"{diff_prix:+,.2f}€".replace(",", " "))

                    with col4:
                        # Espace libre pour futur usage
                        st.metric("", "")

                    # Tableau détaillé des positions restantes
                    st.markdown("#### 📋 Détail des Positions par Ligne d'Achat (FIFO)")

                    # SOLUTION: Récupérer directement les données depuis Supabase pour éviter les corruptions
                    raw_data = (
                        supabase.table("bourse")
                        .select("*")
                        .eq("symbole", symbole_selected.upper())
                        .execute()
                        .data
                    )

                    positions_restantes = business_logic.calculer_positions_restantes_fifo(
                        raw_data, symbole_selected
                    )

                    if positions_restantes:
                        # Préparer les données pour le tableau
                        tableau_positions = []
                        for pos in positions_restantes:
                            date_obj = datetime.strptime(pos["date"], "%Y-%m-%d")
                            tableau_positions.append(
                                {
                                    "Date": date_obj.strftime("%d/%m/%Y"),
                                    "Type": pos["type_operation"],
                                    "Prix €": f"{pos['prix_unitaire']:,.2f}".replace(",", " "),
                                    "Quantité Initiale": f"{pos['quantite_initiale']:.4f}",
                                    "Quantité Restante": f"{pos['quantite_restante']:.4f}",
                                    "Valeur Restante €": f"{pos['montant_restant']:,.2f}".replace(
                                        ",", " "
                                    ),
                                    "% Vendu": (
                                        f"{((pos['quantite_initiale'] - pos['quantite_restante']) / pos['quantite_initiale'] * 100):.1f}%"
                                        if pos["quantite_initiale"] > 0
                                        else "0%"
                                    ),
                                }
                            )

                        df_positions = pd.DataFrame(tableau_positions)
                        st.dataframe(df_positions, use_container_width=True, hide_index=True)

                        # Résumé
                        total_initial = sum([pos["montant_initial"] for pos in positions_restantes])
                        total_restant = sum([pos["montant_restant"] for pos in positions_restantes])
                        total_vendu = total_initial - total_restant
                        st.info(
                            f"📈 **Résumé :** {total_vendu:,.2f}€ vendu sur {total_initial:,.2f}€ initiaux ({total_vendu/total_initial*100:.1f}% du portefeuille initial)".replace(
                                ",", " "
                            )
                        )

                # Graphique d'évolution du prix avec points d'achat
                st.subheader(f"📈 Évolution du prix - {symbole_selected}")

                # Créer le graphique seulement si on a des données de prix
                if perf_symbole and any(inv.get("prix_actuel") for inv in perf_symbole):

                    # Préparer les données pour le graphique
                    dates_achat = [
                        datetime.strptime(inv["date"], "%Y-%m-%d")
                        for inv in investissements_symbole
                    ]
                    prix_achat = [inv["prix_unitaire"] for inv in investissements_symbole]
                    montants_achat = [inv["montant"] for inv in investissements_symbole]
                    types_operation = [
                        inv.get("type_operation", "Achat") for inv in investissements_symbole
                    ]

                    # Prix actuel (on prend le premier disponible)
                    prix_actuel = next(
                        (inv["prix_actuel"] for inv in perf_symbole if inv.get("prix_actuel")), 0
                    )

                    fig = go.Figure()

                    # Ligne horizontale pour le prix actuel
                    fig.add_hline(
                        y=prix_actuel,
                        line_dash="dash",
                        line_color="blue",
                        annotation_text=f"Prix actuel: {prix_actuel:,.2f}€".replace(",", " "),
                        annotation_position="bottom right",
                    )

                    # Séparer les données par type d'opération
                    types_uniques = list(set(types_operation))
                    colors = {
                        "Achat": "#22C55E",
                        "RoundUP": "#22C55E",
                        "SaveBack": "#22C55E",
                        "Vente": "#EF4444",
                    }
                    shapes = {
                        "Achat": "circle",
                        "RoundUP": "diamond",
                        "SaveBack": "square",
                        "Vente": "triangle-down",
                    }

                    for type_op in types_uniques:
                        # Filtrer les données pour ce type d'opération
                        indices = [i for i, t in enumerate(types_operation) if t == type_op]
                        dates_type = [dates_achat[i] for i in indices]
                        prix_type = [prix_achat[i] for i in indices]
                        montants_type = [montants_achat[i] for i in indices]

                        color = colors.get(type_op, "gray")
                        shape = shapes.get(type_op, "circle")

                        # Préparer les hover texts - TEMPORAIREMENT COMMENTÉ
                        # hover_texts = []
                        # for date, prix, montant in zip(dates_type, prix_type, montants_type):
                        #     base_text = f"Date: {date.strftime('%d/%m/%Y')}<br>Type: {type_op}<br>Prix: {prix:,.2f}€<br>Montant: {montant:,.2f}€".replace(",", " ")
                        #
                        #     if type_op == "Vente":
                        #         # Pour les ventes, ajouter le PnL réalisé
                        #         pnl_realise_data = st.session_state.price_service.calculate_realized_pnl(
                        #             data["bourse"], symbole_selected
                        #         )
                        #         base_text += f"<br>PnL réalisé: {pnl_realise_data['pnl_realise_montant']:+,.2f}€".replace(",", " ")
                        #
                        #     hover_texts.append(base_text)

                        # Version simplifiée temporaire
                        hover_texts = [
                            f"Date: {date.strftime('%d/%m/%Y')}<br>Type: {type_op}<br>Prix: {prix:,.2f}€<br>Montant: {montant:,.2f}€".replace(
                                ",", " "
                            )
                            for date, prix, montant in zip(dates_type, prix_type, montants_type)
                        ]

                        fig.add_trace(
                            go.Scatter(
                                x=dates_type,
                                y=prix_type,
                                mode="markers",
                                marker=dict(
                                    size=7.5,
                                    color=color,
                                    symbol=shape,
                                    line=dict(width=2, color=color),
                                ),
                                name=type_op,
                                text=hover_texts,
                                hovertemplate="%{text}<extra></extra>",
                            )
                        )

                    # Ligne du prix moyen d'achat (uniquement si on a des achats)
                    if prix_moyen_achat > 0:
                        fig.add_hline(
                            y=prix_moyen_achat,
                            line_dash="dot",
                            line_color="green",
                            annotation_text=f"Prix moyen d'achat: {prix_moyen_achat:,.2f}€".replace(
                                ",", " "
                            ),
                            annotation_position="top right",
                        )

                    fig.update_layout(
                        title=f"Évolution des prix d'achat - {symbole_selected}",
                        xaxis_title="Date",
                        yaxis_title="Prix (€)",
                        hovermode="closest",
                        showlegend=True,
                        height=400,
                    )

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Graphique non disponible - prix actuels non récupérés")

                # Tableau détaillé des transactions
                st.subheader(f"Historique des transactions - {symbole_selected}")

                df_symbole = pd.DataFrame(perf_symbole)
                # Trier par date AVANT la conversion en format d'affichage
                df_symbole["date"] = pd.to_datetime(df_symbole["date"])
                df_symbole = df_symbole.sort_values(
                    "date", ascending=False
                )  # Plus récent en premier
                df_symbole["date"] = df_symbole["date"].dt.strftime("%d/%m/%Y")

                # Préparer les colonnes d'affichage
                colonnes_base = ["date", "quantite", "prix_unitaire", "montant"]

                # Ajouter type_operation si disponible
                if "type_operation" in df_symbole.columns:
                    colonnes_base.insert(1, "type_operation")

                df_display_symbole = df_symbole[colonnes_base].copy()

                # Formatage
                df_display_symbole["montant"] = df_display_symbole["montant"].apply(
                    lambda x: f"{x:,.2f}€".replace(",", " ")
                )
                df_display_symbole["prix_unitaire"] = df_display_symbole["prix_unitaire"].apply(
                    lambda x: f"{x:,.2f}€".replace(",", " ")
                )
                df_display_symbole["quantite"] = df_display_symbole["quantite"].apply(
                    lambda x: f"{x:.4f}"
                )

                # Ajouter les colonnes de performance si disponibles
                if (
                    "prix_actuel" in df_symbole.columns
                    and "pnl_montant" in df_symbole.columns
                    and "pnl_pourcentage" in df_symbole.columns
                ):
                    df_display_symbole["prix_actuel"] = df_symbole["prix_actuel"].apply(
                        lambda x: f"{x:,.2f}€".replace(",", " ") if x is not None else "N/A"
                    )
                    df_display_symbole["valeur_actuelle"] = df_symbole["valeur_actuelle"].apply(
                        lambda x: f"{x:,.2f}€".replace(",", " ")
                    )
                    df_display_symbole["pnl_montant"] = df_symbole["pnl_montant"].apply(
                        lambda x: f"{x:+,.2f}€".replace(",", " ")
                    )
                    df_display_symbole["pnl_pourcentage"] = df_symbole["pnl_pourcentage"].apply(
                        lambda x: f"{x:+.1f}%"
                    )

                    # Renommer les colonnes
                    if "type_operation" in df_symbole.columns:
                        df_display_symbole.columns = [
                            "Date",
                            "Type",
                            "Quantité",
                            "Prix Achat",
                            "Investi",
                            "Prix Actuel",
                            "Valeur Actuelle",
                            "P&L €",
                            "P&L %",
                        ]
                    else:
                        df_display_symbole.columns = [
                            "Date",
                            "Quantité",
                            "Prix Achat",
                            "Investi",
                            "Prix Actuel",
                            "Valeur Actuelle",
                            "P&L €",
                            "P&L %",
                        ]

                    # Appliquer le style conditionnel
                    def color_pnl(val):
                        if "+" in str(val):
                            return "color: green"
                        elif "-" in str(val):
                            return "color: red"
                        return ""

                    styled_df_symbole = df_display_symbole.style.map(
                        color_pnl, subset=["P&L €", "P&L %"]
                    )
                    st.dataframe(styled_df_symbole, use_container_width=True)
                else:
                    if "type_operation" in df_symbole.columns:
                        df_display_symbole.columns = [
                            "Date",
                            "Type",
                            "Quantité",
                            "Prix Achat",
                            "Investi",
                        ]
                    else:
                        df_display_symbole.columns = [
                            "Date",
                            "Quantité",
                            "Prix Achat",
                            "Investi",
                        ]
                    st.dataframe(df_display_symbole, use_container_width=True)

    with tab_crypto:
        st.header("Investissements Crypto")

        # Métriques spécifiques crypto
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
        with col_m1:
            st.metric("Budget Crypto", f"{budget_crypto:,}€".replace(",", " "))
        with col_m2:
            st.metric("Investi Crypto", f"{total_investi_crypto:,.2f}€".replace(",", " "))
        with col_m3:
            st.metric("Restant Crypto", f"{budget_restant_crypto:,.2f}€".replace(",", " "))
        with col_m4:
            # Calculer la valeur actuelle à partir des données individuelles si disponibles
            crypto_cache_key = f"crypto_perf_{len(data['crypto'])}"
            crypto_with_perf = st.session_state.get(crypto_cache_key)

            if crypto_with_perf and any(inv.get("valeur_actuelle") for inv in crypto_with_perf):
                valeur_actuelle_crypto = sum(
                    inv.get("valeur_actuelle", inv["montant"]) for inv in crypto_with_perf
                )
                st.metric("Valeur Actuelle", f"{valeur_actuelle_crypto:,.2f}€".replace(",", " "))
            elif portfolio_summary and portfolio_summary["crypto"]["valeur_actuelle"] > 0:
                valeur_actuelle_crypto = portfolio_summary["crypto"]["valeur_actuelle"]
                st.metric("Valeur Actuelle", f"{valeur_actuelle_crypto:,.2f}€".replace(",", " "))
            else:
                st.metric("Valeur Actuelle", f"{total_investi_crypto:,.2f}€".replace(",", " "))
        with col_m5:
            # Calculer le P&L à partir des données individuelles si disponibles
            if crypto_with_perf and any(
                inv.get("pnl_montant") is not None for inv in crypto_with_perf
            ):
                pnl_crypto = sum(
                    inv.get("pnl_montant", 0)
                    for inv in crypto_with_perf
                    if inv.get("pnl_montant") is not None
                )
                pnl_pct_crypto = (
                    (pnl_crypto / total_investi_crypto * 100) if total_investi_crypto > 0 else 0
                )
                st.metric(
                    "P&L Total",
                    f"{pnl_crypto:+,.2f}€".replace(",", " "),
                    delta=f"{pnl_pct_crypto:+.1f}%",
                )
            elif portfolio_summary and portfolio_summary["crypto"]["pnl_montant"] is not None:
                pnl_crypto = portfolio_summary["crypto"]["pnl_montant"]
                pnl_pct_crypto = portfolio_summary["crypto"]["pnl_pourcentage"]
                st.metric(
                    "P&L Total",
                    f"{pnl_crypto:+,.2f}€".replace(",", " "),
                    delta=f"{pnl_pct_crypto:+.1f}%",
                )
            else:
                st.metric("P&L Total", "0€", delta="0.0%")

        st.markdown("---")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Nouvel investissement")

            # Saisie du symbole avec liste déroulante
            existing_symbols_crypto = get_existing_symbols(data, "crypto")

            if existing_symbols_crypto:
                # Utiliser un selectbox avec les symboles existants + option "Autre"
                crypto_options = existing_symbols_crypto + ["🆕 Autre symbole..."]
                symbole_choice_crypto = st.selectbox(
                    "Symbole",
                    options=crypto_options,
                    index=None,
                    placeholder="-- Choisir un symbole --",
                    help="Choisissez un symbole existant ou 'Autre symbole...' "
                    "pour saisir manuellement",
                    key="crypto_symbole_select",
                )

                if symbole_choice_crypto == "🆕 Autre symbole...":
                    symbole_crypto = st.text_input(
                        "",
                        placeholder="Ex: BTC, ETH, ADA...",
                        help="Tapez le nom ou symbole de la crypto",
                        key="crypto_symbole_input",
                        label_visibility="collapsed",
                    )
                elif symbole_choice_crypto is not None:
                    symbole_crypto = symbole_choice_crypto
                else:
                    symbole_crypto = ""
            else:
                # Si aucun symbole existant, saisie directe
                symbole_crypto = st.text_input(
                    "Symbole",
                    placeholder="Ex: BTC, ETH, ADA...",
                    help="Tapez le nom ou symbole de la crypto",
                    key="crypto_symbole_input",
                )
            hors_budget_crypto = st.checkbox(
                "Hors budget (conversion/existant)",
                help="Cochez si c'est un investissement existant "
                "ou une conversion qui ne doit pas être déduit du budget",
                key="crypto_hors_budget",
            )

            # Type d'opération
            type_operation_crypto = st.selectbox(
                "Type d'opération",
                options=["Achat", "Vente", "RoundUP", "SaveBack"],
                index=0,
                help="Sélectionnez le type d'opération (achat, vente, roundup, ou saveback)",
                key="crypto_type_operation",
            )

            montant_crypto = st.number_input(
                "Montant (€)",
                min_value=0.0,
                value=None,
                step=10.0,
                key="crypto_montant",
                help="Saisissez le montant de votre investissement",
            )
            date_crypto = st.date_input("Date d'achat", key="crypto_date")
            prix_unitaire_crypto = st.number_input(
                "Prix unitaire (€)", min_value=0.0, value=None, step=0.01, key="crypto_prix"
            )

            if st.button("Ajouter Investissement Crypto"):
                if symbole_crypto and (montant_crypto or 0) > 0 and (prix_unitaire_crypto or 0) > 0:

                    if type_operation_crypto == "Vente":
                        # Validation spécifique pour les ventes
                        quantite_vente = montant_crypto / prix_unitaire_crypto
                        erreurs = business_logic.valider_donnees_vente(
                            montant_crypto,
                            prix_unitaire_crypto,
                            symbole_crypto,
                            quantite_vente,
                            data["crypto"],
                        )

                        if erreurs:
                            for erreur in erreurs:
                                st.error(erreur)
                        else:
                            # Créer les données de vente
                            donnees_vente = business_logic.creer_donnees_vente(
                                date_crypto.isoformat(),
                                symbole_crypto,
                                montant_crypto,
                                prix_unitaire_crypto,
                            )

                            try:
                                supabase.table("crypto").insert(donnees_vente).execute()

                                # Recharger les données
                                data = load_data()
                                save_data(data)

                                # Vider tous les caches de performance qui pourraient être corrompus
                                keys_to_remove = [
                                    key
                                    for key in st.session_state.keys()
                                    if "perf" in key or "cache" in key
                                ]
                                for key in keys_to_remove:
                                    del st.session_state[key]

                                st.success("Vente crypto ajoutée!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur lors de l'ajout de la vente crypto: {e}")
                    else:
                        # Validation standard pour les achats
                        erreurs = business_logic.valider_donnees_investissement(
                            montant_crypto, prix_unitaire_crypto, symbole_crypto
                        )

                        if erreurs:
                            for erreur in erreurs:
                                st.error(erreur)
                        else:
                            # Créer les données d'investissement standard
                            donnees_investissement = business_logic.creer_donnees_investissement(
                                date_crypto.isoformat(),
                                symbole_crypto,
                                montant_crypto,
                                prix_unitaire_crypto,
                                hors_budget_crypto,
                            )
                            # Ajouter le type d'opération
                            donnees_investissement["type_operation"] = type_operation_crypto

                            try:
                                supabase.table("crypto").insert(donnees_investissement).execute()

                                # Recharger les données
                                data = load_data()
                                save_data(data)
                                st.success("Investissement crypto ajouté!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur lors de l'ajout de l'investissement crypto: {e}")

        with col2:
            if data["crypto"]:
                st.subheader("Portfolio Crypto")

                # Calculer les performances avec prix actuels seulement si nécessaire
                crypto_cache_key = f"crypto_perf_{len(data['crypto'])}"
                if crypto_cache_key not in st.session_state:
                    with st.spinner("Récupération des prix crypto actuels..."):
                        crypto_with_perf = (
                            st.session_state.price_service.calculate_investment_performance(
                                data["crypto"], "crypto"
                            )
                        )
                        st.session_state[crypto_cache_key] = crypto_with_perf
                else:
                    crypto_with_perf = st.session_state[crypto_cache_key]

                if crypto_with_perf:
                    df_crypto = pd.DataFrame(crypto_with_perf)
                    # Trier par date AVANT la conversion en format d'affichage
                    df_crypto["date"] = pd.to_datetime(df_crypto["date"])
                    df_crypto = df_crypto.sort_values(
                        "date", ascending=False
                    )  # Plus récent en premier
                    df_crypto["date"] = df_crypto["date"].dt.strftime("%d/%m/%Y")

                    # Préparer les colonnes d'affichage
                    colonnes_base = ["date", "symbole", "quantite", "prix_unitaire", "montant"]

                    # Ajouter type_operation si disponible
                    if "type_operation" in df_crypto.columns:
                        colonnes_base.insert(2, "type_operation")

                    df_display = df_crypto[colonnes_base].copy()

                    # Formatage de base d'abord
                    df_display["montant"] = df_display["montant"].apply(
                        lambda x: f"{x:,.2f}€".replace(",", " ")
                    )
                    df_display["prix_unitaire"] = df_display["prix_unitaire"].apply(
                        lambda x: f"{x:,.2f}€".replace(",", " ")
                    )
                    df_display["quantite"] = df_display["quantite"].apply(lambda x: f"{x:.8f}")

                    # Ajouter les colonnes de performance si disponibles
                    styled_df = df_display  # Par défaut, pas de style
                    if (
                        "prix_actuel" in df_crypto.columns
                        and "pnl_montant" in df_crypto.columns
                        and "pnl_pourcentage" in df_crypto.columns
                    ):
                        df_display["prix_actuel"] = df_crypto["prix_actuel"].apply(
                            lambda x: f"{x:,.2f}€".replace(",", " ") if x is not None else "N/A"
                        )
                        df_display["valeur_actuelle"] = df_crypto["valeur_actuelle"].apply(
                            lambda x: f"{x:,.2f}€".replace(",", " ")
                        )
                        df_display["pnl_montant"] = df_crypto["pnl_montant"].apply(
                            lambda x: f"{x:+,.2f}€".replace(",", " ")
                        )
                        df_display["pnl_pourcentage"] = df_crypto["pnl_pourcentage"].apply(
                            lambda x: f"{x:+.1f}%"
                        )

                        # Renommer les colonnes d'abord
                        if "type_operation" in df_crypto.columns:
                            df_display.columns = [
                                "Date",
                                "Symbole",
                                "Type",
                                "Quantité",
                                "Prix Achat",
                                "Investi",
                                "Prix Actuel",
                                "Valeur Actuelle",
                                "P&L €",
                                "P&L %",
                            ]
                        else:
                            df_display.columns = [
                                "Date",
                                "Symbole",
                                "Quantité",
                                "Prix Achat",
                                "Investi",
                                "Prix Actuel",
                                "Valeur Actuelle",
                                "P&L €",
                                "P&L %",
                            ]

                        # Appliquer un style conditionnel pour les P&L
                        def color_pnl(val):
                            if "+" in str(val):
                                return "color: green"
                            elif "-" in str(val):
                                return "color: red"
                            return ""

                        # Appliquer le style maintenant que toutes les colonnes sont formatées
                        styled_df = df_display.style.map(color_pnl, subset=["P&L €", "P&L %"])
                        st.dataframe(styled_df, use_container_width=True)
                    else:
                        if "type_operation" in df_crypto.columns:
                            df_display.columns = [
                                "Date",
                                "Symbole",
                                "Type",
                                "Quantité",
                                "Prix Achat",
                                "Investi",
                            ]
                        else:
                            df_display.columns = [
                                "Date",
                                "Symbole",
                                "Quantité",
                                "Prix Achat",
                                "Investi",
                            ]
                        st.dataframe(df_display, use_container_width=True)
                        st.warning("Impossible de récupérer les prix actuels")

            else:
                st.info("Aucun investissement crypto enregistré")

        # Section Deep Dive - en dehors des colonnes pour être centrée
        if data["crypto"]:
            st.markdown("---")

            # Section Deep Dive
            st.subheader("📊 Deep Dive")

            # Récupérer les symboles uniques
            symboles_uniques_crypto = sorted(list(set([inv["symbole"] for inv in data["crypto"]])))

            # Récupérer la sélection précédente si elle existe
            default_index_crypto = None
            if "crypto_deep_dive_symbol" in st.session_state:
                previous_symbol_crypto = st.session_state.crypto_deep_dive_symbol
                if previous_symbol_crypto in symboles_uniques_crypto:
                    default_index_crypto = symboles_uniques_crypto.index(previous_symbol_crypto)

            symbole_selected_crypto = st.selectbox(
                "Sélectionner une crypto pour analyse détaillée",
                options=symboles_uniques_crypto,
                index=default_index_crypto,
                placeholder="-- Choisir une crypto --",
                key="crypto_deep_dive_select",
            )

            # Sauvegarder la sélection dans session_state
            if symbole_selected_crypto:
                st.session_state.crypto_deep_dive_symbol = symbole_selected_crypto

            if symbole_selected_crypto:
                # Récupérer les données de performance si disponibles
                crypto_cache_key = f"crypto_perf_{len(data['crypto'])}"
                crypto_with_perf = st.session_state.get(crypto_cache_key)

                # Filtrer les investissements pour ce symbole
                investissements_symbole_crypto = [
                    inv for inv in data["crypto"] if inv["symbole"] == symbole_selected_crypto
                ]

                if crypto_with_perf:
                    perf_symbole_crypto = [
                        inv for inv in crypto_with_perf if inv["symbole"] == symbole_selected_crypto
                    ]
                else:
                    perf_symbole_crypto = investissements_symbole_crypto

                # Calculer les statistiques
                # Quantité réelle disponible (achats - ventes)
                quantite_disponible_crypto = business_logic.calculer_quantite_disponible(
                    data["crypto"], symbole_selected_crypto
                )

                # Calculs séparés pour achats et ventes
                achats_symbole_crypto = [
                    inv
                    for inv in investissements_symbole_crypto
                    if inv.get("type_operation") != "Vente"
                ]
                ventes_symbole_crypto = [
                    inv
                    for inv in investissements_symbole_crypto
                    if inv.get("type_operation") == "Vente"
                ]

                # Total investi = somme des achats seulement (les ventes ne comptent pas comme investissement)
                total_investi_symbole_crypto = sum(
                    [inv["montant"] for inv in achats_symbole_crypto]
                )

                # Prix moyen d'achat basé sur les achats uniquement
                prix_moyen_achat_crypto = (
                    total_investi_symbole_crypto
                    / sum([inv["quantite"] for inv in achats_symbole_crypto])
                    if achats_symbole_crypto
                    else 0
                )

                # PnL réalisé via FIFO
                pnl_realise_data_crypto = st.session_state.price_service.calculate_realized_pnl(
                    data["crypto"], symbole_selected_crypto
                )

                # Performance globale du titre
                if perf_symbole_crypto and any(
                    inv.get("valeur_actuelle") for inv in perf_symbole_crypto
                ):
                    # Valeur actuelle = somme des valeurs actuelles des achats seulement (ventes = 0)
                    perf_achats_crypto = [
                        inv for inv in perf_symbole_crypto if inv.get("type_operation") != "Vente"
                    ]
                    valeur_actuelle_symbole_crypto = sum(
                        [inv.get("valeur_actuelle", inv["montant"]) for inv in perf_achats_crypto]
                    )

                    # PnL non réalisé (différence valeur actuelle vs investissement)
                    pnl_non_realise_crypto = (
                        valeur_actuelle_symbole_crypto - total_investi_symbole_crypto
                    )

                    # PnL total = réalisé + non réalisé
                    pnl_symbole_crypto = (
                        pnl_realise_data_crypto["pnl_realise_montant"] + pnl_non_realise_crypto
                    )
                    pnl_pct_symbole_crypto = (
                        (pnl_symbole_crypto / total_investi_symbole_crypto * 100)
                        if total_investi_symbole_crypto > 0
                        else 0
                    )

                    # Première ligne : Métriques principales
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric(
                            "Total investi",
                            f"{total_investi_symbole_crypto:,.2f}€".replace(",", " "),
                        )

                    with col2:
                        st.metric(
                            "Valeur actuelle",
                            f"{valeur_actuelle_symbole_crypto:,.2f}€".replace(",", " "),
                        )

                    with col3:
                        st.metric("P&L %", "", delta=f"{pnl_pct_symbole_crypto:+.1f}%")

                    with col4:
                        st.metric(
                            "P&L €", "", delta=f"{pnl_symbole_crypto:+,.2f}€".replace(",", " ")
                        )

                    # Affichage détaillé du PnL si il y a des ventes
                    if ventes_symbole_crypto:
                        st.markdown("#### 💰 Analyse PnL Réalisé vs Non Réalisé")

                        # Première ligne : PnL
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            pnl_realise_crypto = pnl_realise_data_crypto["pnl_realise_montant"]
                            st.metric(
                                "PnL Réalisé €", f"{pnl_realise_crypto:+,.2f}€".replace(",", " ")
                            )

                        with col2:
                            pnl_realise_pct_crypto = pnl_realise_data_crypto[
                                "pnl_realise_pourcentage"
                            ]
                            st.metric("PnL Réalisé %", f"{pnl_realise_pct_crypto:+.1f}%")

                        with col3:
                            st.metric(
                                "PnL Non Réalisé €",
                                f"{pnl_non_realise_crypto:+,.2f}€".replace(",", " "),
                            )

                        with col4:
                            quantite_vendue_crypto = pnl_realise_data_crypto[
                                "quantite_vendue_totale"
                            ]
                            st.metric("Quantité Vendue", f"{quantite_vendue_crypto:.8f}")

                        # Deuxième ligne : Prix moyens
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            prix_moyen_vente_crypto = pnl_realise_data_crypto["prix_moyen_vente"]
                            st.metric(
                                "Prix Moyen Vente",
                                f"{prix_moyen_vente_crypto:,.2f}€".replace(",", " "),
                            )

                        with col2:
                            prix_moyen_achat_vendu_crypto = pnl_realise_data_crypto[
                                "prix_moyen_achat_vendu"
                            ]
                            st.metric(
                                "Prix Moyen Achat Vendu",
                                f"{prix_moyen_achat_vendu_crypto:,.2f}€".replace(",", " "),
                            )

                        with col3:
                            # Différence de prix
                            diff_prix_crypto = (
                                prix_moyen_vente_crypto - prix_moyen_achat_vendu_crypto
                            )
                            st.metric(
                                "Différence Prix", f"{diff_prix_crypto:+,.2f}€".replace(",", " ")
                            )

                        with col4:
                            # Espace libre pour futur usage
                            st.metric("", "")

                        # Tableau détaillé des positions restantes
                        st.markdown("#### 📋 Détail des Positions par Ligne d'Achat (FIFO)")
                        # SOLUTION: Récupérer directement les données depuis Supabase pour éviter les corruptions
                        raw_data_crypto = (
                            supabase.table("crypto")
                            .select("*")
                            .eq("symbole", symbole_selected_crypto.upper())
                            .execute()
                            .data
                        )

                        positions_restantes_crypto = (
                            business_logic.calculer_positions_restantes_fifo(
                                raw_data_crypto, symbole_selected_crypto
                            )
                        )

                        if positions_restantes_crypto:
                            # Préparer les données pour le tableau
                            tableau_positions_crypto = []
                            for pos in positions_restantes_crypto:
                                date_obj = datetime.strptime(pos["date"], "%Y-%m-%d")
                                tableau_positions_crypto.append(
                                    {
                                        "Date": date_obj.strftime("%d/%m/%Y"),
                                        "Type": pos["type_operation"],
                                        "Prix €": f"{pos['prix_unitaire']:,.2f}".replace(",", " "),
                                        "Quantité Initiale": f"{pos['quantite_initiale']:.8f}",
                                        "Quantité Restante": f"{pos['quantite_restante']:.8f}",
                                        "Valeur Restante €": f"{pos['montant_restant']:,.2f}".replace(
                                            ",", " "
                                        ),
                                        "% Vendu": (
                                            f"{((pos['quantite_initiale'] - pos['quantite_restante']) / pos['quantite_initiale'] * 100):.1f}%"
                                            if pos["quantite_initiale"] > 0
                                            else "0%"
                                        ),
                                    }
                                )

                            df_positions_crypto = pd.DataFrame(tableau_positions_crypto)
                            st.dataframe(
                                df_positions_crypto, use_container_width=True, hide_index=True
                            )

                            # Résumé
                            total_initial_crypto = sum(
                                [pos["montant_initial"] for pos in positions_restantes_crypto]
                            )
                            total_restant_crypto = sum(
                                [pos["montant_restant"] for pos in positions_restantes_crypto]
                            )
                            total_vendu_crypto = total_initial_crypto - total_restant_crypto
                            st.info(
                                f"📈 **Résumé :** {total_vendu_crypto:,.2f}€ vendu sur {total_initial_crypto:,.2f}€ initiaux ({total_vendu_crypto/total_initial_crypto*100:.1f}% du portefeuille initial)".replace(
                                    ",", " "
                                )
                            )

                # Deuxième ligne : Les métriques de détail
                col1, col2, col3 = st.columns(3)

                with col1:
                    if perf_symbole_crypto and any(
                        inv.get("prix_actuel") for inv in perf_symbole_crypto
                    ):
                        prix_actuel_crypto = next(
                            (
                                inv["prix_actuel"]
                                for inv in perf_symbole_crypto
                                if inv.get("prix_actuel")
                            ),
                            0,
                        )
                        st.metric("Prix actuel", f"{prix_actuel_crypto:,.2f}€".replace(",", " "))
                    else:
                        st.metric("Prix actuel", "N/A")

                with col2:
                    st.metric(
                        "Prix moyen d'achat", f"{prix_moyen_achat_crypto:,.2f}€".replace(",", " ")
                    )

                with col3:
                    st.metric("Quantité disponible", f"{quantite_disponible_crypto:.8f}")

                # Graphique d'évolution du prix avec points d'achat
                st.subheader(f"📈 Évolution du prix - {symbole_selected_crypto}")

                # Créer le graphique seulement si on a des données de prix
                if perf_symbole_crypto and any(
                    inv.get("prix_actuel") for inv in perf_symbole_crypto
                ):

                    # Préparer les données pour le graphique
                    dates_achat_crypto = [
                        datetime.strptime(inv["date"], "%Y-%m-%d")
                        for inv in investissements_symbole_crypto
                    ]
                    prix_achat_crypto = [
                        inv["prix_unitaire"] for inv in investissements_symbole_crypto
                    ]
                    montants_achat_crypto = [
                        inv["montant"] for inv in investissements_symbole_crypto
                    ]
                    types_operation_crypto = [
                        inv.get("type_operation", "Achat") for inv in investissements_symbole_crypto
                    ]

                    # Prix actuel (on prend le premier disponible)
                    prix_actuel_crypto = next(
                        (
                            inv["prix_actuel"]
                            for inv in perf_symbole_crypto
                            if inv.get("prix_actuel")
                        ),
                        0,
                    )

                    fig_crypto = go.Figure()

                    # Ligne horizontale pour le prix actuel
                    fig_crypto.add_hline(
                        y=prix_actuel_crypto,
                        line_dash="dash",
                        line_color="blue",
                        annotation_text=f"Prix actuel: {prix_actuel_crypto:,.2f}€".replace(
                            ",", " "
                        ),
                        annotation_position="bottom right",
                    )

                    # Séparer les données par type d'opération
                    types_uniques_crypto = list(set(types_operation_crypto))
                    colors_crypto = {
                        "Achat": "#22C55E",
                        "RoundUP": "#22C55E",
                        "SaveBack": "#22C55E",
                        "Vente": "#EF4444",
                    }
                    shapes_crypto = {
                        "Achat": "circle",
                        "RoundUP": "diamond",
                        "SaveBack": "square",
                        "Vente": "triangle-down",
                    }

                    for type_op in types_uniques_crypto:
                        # Filtrer les données pour ce type d'opération
                        indices = [i for i, t in enumerate(types_operation_crypto) if t == type_op]
                        dates_type = [dates_achat_crypto[i] for i in indices]
                        prix_type = [prix_achat_crypto[i] for i in indices]
                        montants_type = [montants_achat_crypto[i] for i in indices]

                        color = colors_crypto.get(type_op, "#FF6B35")
                        shape = shapes_crypto.get(type_op, "circle")

                        # Préparer les hover texts - TEMPORAIREMENT COMMENTÉ
                        # hover_texts_crypto = []
                        # for date, prix, montant in zip(dates_type, prix_type, montants_type):
                        #     base_text = f"Date: {date.strftime('%d/%m/%Y')}<br>Type: {type_op}<br>Prix: {prix:,.2f}€<br>Montant: {montant:,.2f}€".replace(",", " ")
                        #
                        #     if type_op == "Vente":
                        #         # Pour les ventes, ajouter le PnL réalisé
                        #         pnl_realise_data_crypto = st.session_state.price_service.calculate_realized_pnl(
                        #             data["crypto"], symbole_selected_crypto
                        #         )
                        #         base_text += f"<br>PnL réalisé: {pnl_realise_data_crypto['pnl_realise_montant']:+,.2f}€".replace(",", " ")
                        #
                        #     hover_texts_crypto.append(base_text)

                        # Version simplifiée temporaire
                        hover_texts_crypto = [
                            f"Date: {date.strftime('%d/%m/%Y')}<br>Type: {type_op}<br>Prix: {prix:,.2f}€<br>Montant: {montant:,.2f}€".replace(
                                ",", " "
                            )
                            for date, prix, montant in zip(dates_type, prix_type, montants_type)
                        ]

                        fig_crypto.add_trace(
                            go.Scatter(
                                x=dates_type,
                                y=prix_type,
                                mode="markers",
                                marker=dict(
                                    size=7.5,
                                    color=color,
                                    symbol=shape,
                                    line=dict(width=2, color=color),
                                ),
                                name=type_op,
                                text=hover_texts_crypto,
                                hovertemplate="%{text}<extra></extra>",
                            )
                        )

                    # Ligne du prix moyen d'achat (uniquement si on a des achats)
                    if prix_moyen_achat_crypto > 0:
                        fig_crypto.add_hline(
                            y=prix_moyen_achat_crypto,
                            line_dash="dot",
                            line_color="green",
                            annotation_text=f"Prix moyen d'achat: {prix_moyen_achat_crypto:,.2f}€".replace(
                                ",", " "
                            ),
                            annotation_position="top right",
                        )

                    fig_crypto.update_layout(
                        title=f"Évolution des prix d'achat - {symbole_selected_crypto}",
                        xaxis_title="Date",
                        yaxis_title="Prix (€)",
                        hovermode="closest",
                        showlegend=True,
                        height=400,
                    )

                    st.plotly_chart(fig_crypto, use_container_width=True)
                else:
                    st.info("Graphique non disponible - prix actuels non récupérés")

                # Tableau détaillé des transactions
                st.subheader(f"Historique des transactions - {symbole_selected_crypto}")

                df_symbole_crypto = pd.DataFrame(perf_symbole_crypto)
                # Trier par date AVANT la conversion en format d'affichage
                df_symbole_crypto["date"] = pd.to_datetime(df_symbole_crypto["date"])
                df_symbole_crypto = df_symbole_crypto.sort_values(
                    "date", ascending=False
                )  # Plus récent en premier
                df_symbole_crypto["date"] = df_symbole_crypto["date"].dt.strftime("%d/%m/%Y")

                # Préparer les colonnes d'affichage
                colonnes_base_crypto = ["date", "quantite", "prix_unitaire", "montant"]

                # Ajouter type_operation si disponible
                if "type_operation" in df_symbole_crypto.columns:
                    colonnes_base_crypto.insert(1, "type_operation")

                df_display_symbole_crypto = df_symbole_crypto[colonnes_base_crypto].copy()

                # Formatage
                df_display_symbole_crypto["montant"] = df_display_symbole_crypto["montant"].apply(
                    lambda x: f"{x:,.2f}€".replace(",", " ")
                )
                df_display_symbole_crypto["prix_unitaire"] = df_display_symbole_crypto[
                    "prix_unitaire"
                ].apply(lambda x: f"{x:,.2f}€".replace(",", " "))
                df_display_symbole_crypto["quantite"] = df_display_symbole_crypto["quantite"].apply(
                    lambda x: f"{x:.8f}"
                )

                # Ajouter les colonnes de performance si disponibles
                if (
                    "prix_actuel" in df_symbole_crypto.columns
                    and "pnl_montant" in df_symbole_crypto.columns
                    and "pnl_pourcentage" in df_symbole_crypto.columns
                ):
                    df_display_symbole_crypto["prix_actuel"] = df_symbole_crypto[
                        "prix_actuel"
                    ].apply(lambda x: f"{x:,.2f}€".replace(",", " ") if x is not None else "N/A")
                    df_display_symbole_crypto["valeur_actuelle"] = df_symbole_crypto[
                        "valeur_actuelle"
                    ].apply(lambda x: f"{x:,.2f}€".replace(",", " "))
                    df_display_symbole_crypto["pnl_montant"] = df_symbole_crypto[
                        "pnl_montant"
                    ].apply(lambda x: f"{x:+,.2f}€".replace(",", " "))
                    df_display_symbole_crypto["pnl_pourcentage"] = df_symbole_crypto[
                        "pnl_pourcentage"
                    ].apply(lambda x: f"{x:+.1f}%")

                    # Renommer les colonnes
                    if "type_operation" in df_symbole_crypto.columns:
                        df_display_symbole_crypto.columns = [
                            "Date",
                            "Type",
                            "Quantité",
                            "Prix Achat",
                            "Investi",
                            "Prix Actuel",
                            "Valeur Actuelle",
                            "P&L €",
                            "P&L %",
                        ]
                    else:
                        df_display_symbole_crypto.columns = [
                            "Date",
                            "Quantité",
                            "Prix Achat",
                            "Investi",
                            "Prix Actuel",
                            "Valeur Actuelle",
                            "P&L €",
                            "P&L %",
                        ]

                    # Appliquer le style conditionnel
                    def color_pnl_crypto(val):
                        if "+" in str(val):
                            return "color: green"
                        elif "-" in str(val):
                            return "color: red"
                        return ""

                    styled_df_symbole_crypto = df_display_symbole_crypto.style.map(
                        color_pnl_crypto, subset=["P&L €", "P&L %"]
                    )
                    st.dataframe(styled_df_symbole_crypto, use_container_width=True)
                else:
                    if "type_operation" in df_symbole_crypto.columns:
                        df_display_symbole_crypto.columns = [
                            "Date",
                            "Type",
                            "Quantité",
                            "Prix Achat",
                            "Investi",
                        ]
                    else:
                        df_display_symbole_crypto.columns = [
                            "Date",
                            "Quantité",
                            "Prix Achat",
                            "Investi",
                        ]
                    st.dataframe(df_display_symbole_crypto, use_container_width=True)

    with tab_revenus:
        st.header("Historique des Revenus")

        if data["revenus"]:
            df_revenus = pd.DataFrame(data["revenus"])

            # Conversion du mois en nom
            noms_mois = [
                "Janvier",
                "Février",
                "Mars",
                "Avril",
                "Mai",
                "Juin",
                "Juillet",
                "Août",
                "Septembre",
                "Octobre",
                "Novembre",
                "Décembre",
            ]
            df_revenus["mois_nom"] = df_revenus["mois"].apply(lambda x: noms_mois[x - 1])

            # Tri par année et mois
            df_revenus = df_revenus.sort_values(["annee", "mois"])

            # Affichage du tableau
            st.subheader("Récapitulatif des revenus")

            # Affichage du tableau
            df_display = df_revenus[["annee", "mois_nom", "montant"]].copy()
            df_display["budget_total"] = (
                (
                    df_revenus["investissement_disponible_bourse"]
                    + df_revenus["investissement_disponible_crypto"]
                )
                .round()
                .astype(int)
            )
            df_display.columns = ["Année", "Mois", "Revenu Net (€)", "Budget Investissement (€)"]
            st.dataframe(df_display, use_container_width=True)

            # Métriques de résumé
            col1, col2, col3 = st.columns(3)

            with col1:
                total_revenus = df_revenus["montant"].sum()
                st.metric("Total des Revenus", f"{total_revenus:,.2f}€".replace(",", " "))

            with col2:
                total_investissement_bourse = df_revenus["investissement_disponible_bourse"].sum()
                total_investissement_crypto = df_revenus["investissement_disponible_crypto"].sum()
                total_investissement = total_investissement_bourse + total_investissement_crypto
                st.metric(
                    "Total Budget Investissement", f"{total_investissement:,.2f}€".replace(",", " ")
                )

            with col3:
                nb_mois = len(df_revenus)
                st.metric("Nombre de Mois", f"{nb_mois}")

        else:
            st.info("Aucun revenu enregistré pour le moment")

    with tab_overview:
        st.header("Vue d'ensemble")

        # Calculer les performances globales ici seulement si nécessaire
        if not portfolio_summary and (data["bourse"] or data["crypto"]):
            with st.spinner("Calcul des performances globales..."):
                crypto_with_perf = (
                    st.session_state.price_service.calculate_investment_performance(
                        data["crypto"], "crypto"
                    )
                    if data["crypto"]
                    else []
                )

                bourse_with_perf = (
                    st.session_state.price_service.calculate_investment_performance(
                        data["bourse"], "bourse"
                    )
                    if data["bourse"]
                    else []
                )

                portfolio_summary = st.session_state.price_service.calculate_portfolio_summary(
                    crypto_with_perf, bourse_with_perf
                )

                # Mettre en cache dans la session
                st.session_state.portfolio_summary = portfolio_summary

        if data["bourse"] or data["crypto"]:
            # Section Performances
            if portfolio_summary:
                st.subheader("📊 Performances du Portfolio")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    total_investi = portfolio_summary["total"]["valeur_initiale"]
                    st.metric("Total Investi", f"{total_investi:,.2f}€".replace(",", " "))

                with col2:
                    valeur_actuelle = portfolio_summary["total"]["valeur_actuelle"]
                    st.metric("Valeur Actuelle", f"{valeur_actuelle:,.2f}€".replace(",", " "))

                with col3:
                    pnl_montant = portfolio_summary["total"]["pnl_montant"]
                    st.metric("P&L €", f"{pnl_montant:+,.2f}€".replace(",", " "))

                with col4:
                    pnl_pct = portfolio_summary["total"]["pnl_pourcentage"]
                    st.metric("P&L %", f"{pnl_pct:+.1f}%")

        else:
            st.info("Aucun investissement enregistré pour le moment")


if __name__ == "__main__":
    main()
