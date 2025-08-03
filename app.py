import json
import math
import os
from datetime import date

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

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

    # Bouton pour actualiser les prix
    col_refresh, col_empty = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Actualiser les prix"):
            st.session_state.price_service.clear_cache()
            st.rerun()

    # Calculer les performances globales
    portfolio_summary = None
    if data["bourse"] or data["crypto"]:
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

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Budget Total", f"{budget_total:,}€".replace(",", " "))

    with col2:
        st.metric("Total Investi", f"{total_investi_reel:,.0f}€".replace(",", " "))

    with col3:
        if portfolio_summary:
            valeur_actuelle = portfolio_summary["total"]["valeur_actuelle"]
            st.metric("Valeur Actuelle", f"{valeur_actuelle:,.0f}€".replace(",", " "))
        else:
            st.metric("Valeur Actuelle", f"{total_investi_reel:,.0f}€".replace(",", " "))

    with col4:
        if portfolio_summary:
            pnl_total = portfolio_summary["total"]["pnl_montant"]
            pnl_pct = portfolio_summary["total"]["pnl_pourcentage"]
            delta_color = "normal" if pnl_total >= 0 else "inverse"
            st.metric(
                "P&L Total", f"{pnl_total:+,.0f}€".replace(",", " "), delta=f"{pnl_pct:+.1f}%"
            )
        else:
            st.metric("Total Restant", f"{total_restant:,.0f}€".replace(",", " "))

    st.markdown("---")

    # Tabs pour Bourse et Crypto
    tab_revenus, tab_bourse, tab_crypto, tab_overview = st.tabs(
        ["Revenus", "Bourse", "Crypto", "Vue d'ensemble"]
    )

    with tab_bourse:
        st.header("Investissements Bourse")

        # Métriques spécifiques bourse
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Budget Bourse", f"{budget_bourse:,}€".replace(",", " "))
        with col_m2:
            st.metric("Investi Bourse", f"{total_investi_bourse:,.0f}€".replace(",", " "))
        with col_m3:
            st.metric("Restant Bourse", f"{budget_restant_bourse:,.0f}€".replace(",", " "))

        st.markdown("---")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Nouvel investissement")

            symbole_bourse = st.text_input(
                "Symbole",
                placeholder="Ex: NVIDIA, AAPL, HIWS...",
                key="bourse_symbole",
                help="Tapez le nom ou symbole de l'action. Le système essaiera de le trouver automatiquement.",
            )

            hors_budget_bourse = st.checkbox(
                "Hors budget (conversion/existant)",
                help="Cochez si c'est un investissement existant "
                "ou une conversion qui ne doit pas être déduit du budget",
                key="bourse_hors_budget",
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

            # Bouton de validation du prix (pour tester la recherche)
            if st.button("🔍 Vérifier le symbole", key="check_symbol"):
                if symbole_bourse:
                    with st.spinner(f"Recherche de {symbole_bourse}..."):
                        price, choices = st.session_state.price_service.get_stock_price_with_choice(symbole_bourse)
                        
                        if price is not None:
                            st.success(f"✅ Prix trouvé: {price:.2f}€")
                        elif choices:
                            st.session_state.symbol_choices = choices
                            st.session_state.pending_symbol = symbole_bourse
                            st.info(f"🔍 Plusieurs options trouvées pour '{symbole_bourse}'. Veuillez choisir ci-dessous :")
                            st.rerun()
                        else:
                            st.error(f"❌ Aucun symbole trouvé pour '{symbole_bourse}'")

            # Interface de choix si plusieurs options trouvées
            if hasattr(st.session_state, 'symbol_choices') and st.session_state.symbol_choices:
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
                    key="symbol_choice_radio"
                )
                
                col_choose, col_cancel = st.columns(2)
                
                with col_choose:
                    if st.button("✅ Utiliser ce symbole", key="confirm_choice"):
                        chosen_variant, chosen_price, chosen_market, chosen_company = choices[selected_choice]
                        
                        # Sauvegarder le choix
                        final_price = st.session_state.price_service.save_user_choice(
                            st.session_state.pending_symbol, 
                            chosen_variant, 
                            chosen_company
                        )
                        
                        if final_price:
                            st.success(f"💾 Choix sauvegardé ! {st.session_state.pending_symbol} → {chosen_variant} ({final_price:.2f}€)")
                        
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
                    quantite = montant_bourse / prix_unitaire_bourse
                    try:
                        supabase.table("bourse").insert(
                            {
                                "date": date_bourse.isoformat(),
                                "symbole": symbole_bourse.upper(),
                                "montant": montant_bourse,
                                "prix_unitaire": prix_unitaire_bourse,
                                "quantite": quantite,
                                "hors_budget": hors_budget_bourse,
                            }
                        ).execute()

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

                # Calculer les performances avec prix actuels
                with st.spinner("Récupération des prix actuels..."):
                    bourse_with_perf = (
                        st.session_state.price_service.calculate_investment_performance(
                            data["bourse"], "bourse"
                        )
                    )

                if bourse_with_perf:
                    df_bourse = pd.DataFrame(bourse_with_perf)
                    df_bourse["date"] = pd.to_datetime(df_bourse["date"]).dt.date

                    # Préparer les colonnes d'affichage
                    df_display = df_bourse[
                        ["date", "symbole", "quantite", "prix_unitaire", "montant"]
                    ].copy()

                    # Formatage de base d'abord
                    df_display["montant"] = df_display["montant"].apply(
                        lambda x: f"{x:,.0f}€".replace(",", " ")
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
                            lambda x: f"{x:,.0f}€".replace(",", " ")
                        )
                        df_display["pnl_montant"] = df_bourse["pnl_montant"].apply(
                            lambda x: f"{x:+,.0f}€".replace(",", " ")
                        )
                        df_display["pnl_pourcentage"] = df_bourse["pnl_pourcentage"].apply(
                            lambda x: f"{x:+.1f}%"
                        )

                        # Renommer les colonnes d'abord
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
                        df_display.columns = [
                            "Date",
                            "Symbole",
                            "Quantité",
                            "Prix Achat",
                            "Investi",
                        ]
                        st.dataframe(df_display, use_container_width=True)
                        st.warning("Impossible de récupérer les prix actuels")

                    # Métriques de performance globale bourse
                    if "valeur_actuelle" in df_bourse.columns:
                        total_investi = df_bourse["montant"].sum()
                        total_actuel = df_bourse["valeur_actuelle"].sum()
                        total_pnl = total_actuel - total_investi
                        total_pnl_pct = (
                            (total_pnl / total_investi * 100) if total_investi > 0 else 0
                        )

                        col_perf1, col_perf2, col_perf3 = st.columns(3)
                        with col_perf1:
                            st.metric("Valeur Actuelle", f"{total_actuel:,.0f}€".replace(",", " "))
                        with col_perf2:
                            st.metric(
                                "P&L Total",
                                f"{total_pnl:+,.0f}€".replace(",", " "),
                                delta=f"{total_pnl_pct:+.1f}%",
                            )
                        with col_perf3:
                            if total_pnl >= 0:
                                st.success(f"📈 +{total_pnl_pct:.1f}%")
                            else:
                                st.error(f"📉 {total_pnl_pct:.1f}%")
            else:
                st.info("Aucun investissement bourse enregistré")

    with tab_crypto:
        st.header("Investissements Crypto")

        # Métriques spécifiques crypto
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Budget Crypto", f"{budget_crypto:,}€".replace(",", " "))
        with col_m2:
            st.metric("Investi Crypto", f"{total_investi_crypto:,.0f}€".replace(",", " "))
        with col_m3:
            st.metric("Restant Crypto", f"{budget_restant_crypto:,.0f}€".replace(",", " "))

        st.markdown("---")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Nouvel investissement")

            symbole_crypto = st.selectbox("Symbole", options=["BTC"], key="crypto_symbole")
            hors_budget_crypto = st.checkbox(
                "Hors budget (conversion/existant)",
                help="Cochez si c'est un investissement existant "
                "ou une conversion qui ne doit pas être déduit du budget",
                key="crypto_hors_budget",
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
                    quantite = montant_crypto / prix_unitaire_crypto
                    try:
                        supabase.table("crypto").insert(
                            {
                                "date": date_crypto.isoformat(),
                                "symbole": symbole_crypto.upper(),
                                "montant": montant_crypto,
                                "prix_unitaire": prix_unitaire_crypto,
                                "quantite": quantite,
                                "hors_budget": hors_budget_crypto,
                            }
                        ).execute()

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

                # Calculer les performances avec prix actuels
                with st.spinner("Récupération des prix crypto actuels..."):
                    crypto_with_perf = (
                        st.session_state.price_service.calculate_investment_performance(
                            data["crypto"], "crypto"
                        )
                    )

                if crypto_with_perf:
                    df_crypto = pd.DataFrame(crypto_with_perf)
                    df_crypto["date"] = pd.to_datetime(df_crypto["date"]).dt.date

                    # Préparer les colonnes d'affichage
                    df_display = df_crypto[
                        ["date", "symbole", "quantite", "prix_unitaire", "montant"]
                    ].copy()

                    # Formatage de base d'abord
                    df_display["montant"] = df_display["montant"].apply(
                        lambda x: f"{x:,.0f}€".replace(",", " ")
                    )
                    df_display["prix_unitaire"] = df_display["prix_unitaire"].apply(
                        lambda x: f"{x:,.0f}€".replace(",", " ")
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
                            lambda x: f"{x:,.0f}€".replace(",", " ") if x is not None else "N/A"
                        )
                        df_display["valeur_actuelle"] = df_crypto["valeur_actuelle"].apply(
                            lambda x: f"{x:,.0f}€".replace(",", " ")
                        )
                        df_display["pnl_montant"] = df_crypto["pnl_montant"].apply(
                            lambda x: f"{x:+,.0f}€".replace(",", " ")
                        )
                        df_display["pnl_pourcentage"] = df_crypto["pnl_pourcentage"].apply(
                            lambda x: f"{x:+.1f}%"
                        )

                        # Renommer les colonnes d'abord
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
                        df_display.columns = [
                            "Date",
                            "Symbole",
                            "Quantité",
                            "Prix Achat",
                            "Investi",
                        ]
                        st.dataframe(df_display, use_container_width=True)
                        st.warning("Impossible de récupérer les prix actuels")

                    # Métriques de performance globale crypto
                    if "valeur_actuelle" in df_crypto.columns:
                        total_investi = df_crypto["montant"].sum()
                        total_actuel = df_crypto["valeur_actuelle"].sum()
                        total_pnl = total_actuel - total_investi
                        total_pnl_pct = (
                            (total_pnl / total_investi * 100) if total_investi > 0 else 0
                        )

                        col_perf1, col_perf2, col_perf3 = st.columns(3)
                        with col_perf1:
                            st.metric("Valeur Actuelle", f"{total_actuel:,.0f}€".replace(",", " "))
                        with col_perf2:
                            st.metric(
                                "P&L Total",
                                f"{total_pnl:+,.0f}€".replace(",", " "),
                                delta=f"{total_pnl_pct:+.1f}%",
                            )
                        with col_perf3:
                            if total_pnl >= 0:
                                st.success(f"🚀 +{total_pnl_pct:.1f}%")
                            else:
                                st.error(f"💥 {total_pnl_pct:.1f}%")
            else:
                st.info("Aucun investissement crypto enregistré")

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
                st.metric("Total des Revenus", f"{total_revenus:,.0f}€".replace(",", " "))

            with col2:
                total_investissement_bourse = df_revenus["investissement_disponible_bourse"].sum()
                total_investissement_crypto = df_revenus["investissement_disponible_crypto"].sum()
                total_investissement = total_investissement_bourse + total_investissement_crypto
                st.metric(
                    "Total Budget Investissement", f"{total_investissement:,.0f}€".replace(",", " ")
                )

            with col3:
                nb_mois = len(df_revenus)
                st.metric("Nombre de Mois", f"{nb_mois}")

        else:
            st.info("Aucun revenu enregistré pour le moment")

    with tab_overview:
        st.header("Vue d'ensemble")

        if data["bourse"] or data["crypto"]:
            # Graphique évolution temporelle
            all_investments = []

            for inv in data["bourse"]:
                all_investments.append(
                    {
                        "date": inv["date"],
                        "montant": inv["montant"],
                        "type": "Bourse",
                        "symbole": inv["symbole"],
                    }
                )

            for inv in data["crypto"]:
                all_investments.append(
                    {
                        "date": inv["date"],
                        "montant": inv["montant"],
                        "type": "Crypto",
                        "symbole": inv["symbole"],
                    }
                )

            if all_investments:
                df_all = pd.DataFrame(all_investments)
                df_all["date"] = pd.to_datetime(df_all["date"])
                df_all = df_all.sort_values("date")
                df_all["montant_cumule"] = df_all["montant"].cumsum()

        else:
            st.info("Aucun investissement enregistré pour le moment")


if __name__ == "__main__":
    main()
