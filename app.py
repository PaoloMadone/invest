import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import json
import os
import math

st.set_page_config(
    page_title="Tracker d'Investissements",
    page_icon="📈",
    layout="wide"
)

DATA_FILE = "investments_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"revenus": [], "bourse": [], "crypto": []}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    st.title("📈 Tracker d'Investissements")
    st.markdown("---")
    
    data = load_data()
    
    # Sidebar pour saisie des revenus
    with st.sidebar:
        st.header("💰 Saisie des Revenus")
        
        revenu_net = st.number_input(
            "Revenu net mensuel (€)",
            min_value=0,
            value=0,
            step=100,
            help="Saisissez votre revenu net mensuel"
        )
        
        col_mois, col_annee = st.columns(2)
        with col_mois:
            mois_revenu = st.selectbox(
                "Mois",
                options=list(range(1, 13)),
                format_func=lambda x: [
                    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
                ][x-1],
                index=date.today().month - 1
            )
        with col_annee:
            annee_revenu = st.number_input(
                "Année",
                min_value=2020,
                max_value=2030,
                value=date.today().year,
                step=1
            )
        
        if st.button("💾 Enregistrer Revenu"):
            if revenu_net > 0:
                periode_actuelle = f"{annee_revenu}-{mois_revenu:02d}"
                
                # Vérifier si le revenu pour cette période existe déjà
                periode_existante = any(r["periode"] == periode_actuelle for r in data["revenus"])
                
                if periode_existante:
                    st.error(f"Un revenu pour {periode_actuelle} existe déjà!")
                else:
                    montant_investissement_bourse = round(revenu_net * 0.10, 2)
                    montant_investissement_crypto = round(revenu_net * 0.10, 2)
                    data["revenus"].append({
                        "mois": mois_revenu,
                        "annee": int(annee_revenu),
                        "periode": periode_actuelle,
                        "montant": revenu_net,
                        "investissement_disponible_bourse": montant_investissement_bourse,
                        "investissement_disponible_crypto": montant_investissement_crypto
                    })
                    save_data(data)
                    st.success(f"Revenu enregistré! {montant_investissement_bourse:.2f}€ pour bourse, {montant_investissement_crypto:.2f}€ pour crypto")
                    st.rerun()
    
    # Calcul des budgets d'investissement séparés
    budget_bourse_brut = sum([r.get("investissement_disponible_bourse", r.get("investissement_disponible", 0)) for r in data["revenus"]])
    budget_crypto_brut = sum([r.get("investissement_disponible_crypto", r.get("investissement_disponible", 0)) for r in data["revenus"]])
    budget_bourse = math.ceil(budget_bourse_brut)
    budget_crypto = math.ceil(budget_crypto_brut)
    budget_total = budget_bourse + budget_crypto
    
    budget_utilise_bourse = sum([b["montant"] for b in data["bourse"] if not b.get("hors_budget", False)])
    budget_utilise_crypto = sum([c["montant"] for c in data["crypto"] if not c.get("hors_budget", False)])
    
    budget_restant_bourse = budget_bourse - budget_utilise_bourse
    budget_restant_crypto = budget_crypto - budget_utilise_crypto
    budget_restant = budget_restant_bourse + budget_restant_crypto
    
    # Métriques globales
    total_investi = budget_utilise_bourse + budget_utilise_crypto
    total_restant = budget_restant_bourse + budget_restant_crypto
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("💼 Budget Total", f"{budget_total}€")
        
    with col2:
        st.metric("📊 Total Investi", f"{total_investi:.2f}€")
        
    with col3:
        st.metric("💵 Total Restant", f"{total_restant:.2f}€")
    
    st.markdown("---")
    
    # Tabs pour Bourse et Crypto
    tab_bourse, tab_crypto, tab_revenus, tab_overview = st.tabs(["📊 Bourse", "₿ Crypto", "💰 Revenus", "📈 Vue d'ensemble"])
    
    with tab_bourse:
        st.header("📊 Investissements Bourse")
        
        # Métriques spécifiques bourse
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("💼 Budget Bourse", f"{budget_bourse}€")
        with col_m2:
            st.metric("📊 Investi Bourse", f"{budget_utilise_bourse:.2f}€")
        with col_m3:
            st.metric("💵 Restant Bourse", f"{budget_restant_bourse:.2f}€")
        
        st.markdown("---")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Nouvel investissement")
            
            symbole_bourse = st.selectbox(
                "Symbole",
                options=["HIWS"],
                key="bourse_symbole"
            )
            
            hors_budget_bourse = st.checkbox(
                "💰 Hors budget (conversion/existant)",
                help="Cochez si c'est un investissement existant ou une conversion qui ne doit pas être déduit du budget",
                key="bourse_hors_budget"
            )
            
            montant_bourse = st.number_input(
                "Montant (€)",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key="bourse_montant",
                help="Saisissez le montant de votre investissement"
            )
            date_bourse = st.date_input("Date d'achat", key="bourse_date")
            prix_unitaire_bourse = st.number_input("Prix unitaire (€)", min_value=0.0, value=0.0, step=0.01, key="bourse_prix")
            
            if st.button("➕ Ajouter Investissement Bourse"):
                if symbole_bourse and montant_bourse > 0 and prix_unitaire_bourse > 0:
                    quantite = montant_bourse / prix_unitaire_bourse
                    data["bourse"].append({
                        "date": date_bourse.isoformat(),
                        "symbole": symbole_bourse.upper(),
                        "montant": montant_bourse,
                        "prix_unitaire": prix_unitaire_bourse,
                        "quantite": quantite,
                        "hors_budget": hors_budget_bourse
                    })
                    save_data(data)
                    st.success("Investissement bourse ajouté!")
                    st.rerun()
        
        with col2:
            if data["bourse"]:
                df_bourse = pd.DataFrame(data["bourse"])
                df_bourse["date"] = pd.to_datetime(df_bourse["date"])
                
                st.subheader("Portfolio Bourse")
                st.dataframe(df_bourse, use_container_width=True)
                
                # Graphique répartition par symbole
                fig_pie = px.pie(
                    df_bourse,
                    values="montant",
                    names="symbole",
                    title="Répartition des investissements bourse"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Aucun investissement bourse enregistré")
    
    with tab_crypto:
        st.header("₿ Investissements Crypto")
        
        # Métriques spécifiques crypto
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("₿ Budget Crypto", f"{budget_crypto}€")
        with col_m2:
            st.metric("₿ Investi Crypto", f"{budget_utilise_crypto:.2f}€")
        with col_m3:
            st.metric("💰 Restant Crypto", f"{budget_restant_crypto:.2f}€")
        
        st.markdown("---")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Nouvel investissement")
            
            symbole_crypto = st.selectbox(
                "Symbole",
                options=["BTC"],
                key="crypto_symbole"
            )
            hors_budget_crypto = st.checkbox(
                "💰 Hors budget (conversion/existant)",
                help="Cochez si c'est un investissement existant ou une conversion qui ne doit pas être déduit du budget",
                key="crypto_hors_budget"
            )
            
            montant_crypto = st.number_input(
                "Montant (€)",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key="crypto_montant",
                help="Saisissez le montant de votre investissement"
            )
            date_crypto = st.date_input("Date d'achat", key="crypto_date")
            prix_unitaire_crypto = st.number_input("Prix unitaire (€)", min_value=0.0, value=0.0, step=0.01, key="crypto_prix")
            
            if st.button("➕ Ajouter Investissement Crypto"):
                if symbole_crypto and montant_crypto > 0 and prix_unitaire_crypto > 0:
                    quantite = montant_crypto / prix_unitaire_crypto
                    data["crypto"].append({
                        "date": date_crypto.isoformat(),
                        "symbole": symbole_crypto.upper(),
                        "montant": montant_crypto,
                        "prix_unitaire": prix_unitaire_crypto,
                        "quantite": quantite,
                        "hors_budget": hors_budget_crypto
                    })
                    save_data(data)
                    st.success("Investissement crypto ajouté!")
                    st.rerun()
        
        with col2:
            if data["crypto"]:
                df_crypto = pd.DataFrame(data["crypto"])
                df_crypto["date"] = pd.to_datetime(df_crypto["date"])
                
                st.subheader("Portfolio Crypto")
                st.dataframe(df_crypto, use_container_width=True)
                
                # Graphique répartition par symbole
                fig_pie = px.pie(
                    df_crypto,
                    values="montant",
                    names="symbole",
                    title="Répartition des investissements crypto"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Aucun investissement crypto enregistré")
    
    with tab_revenus:
        st.header("💰 Historique des Revenus")
        
        if data["revenus"]:
            df_revenus = pd.DataFrame(data["revenus"])
            
            # Conversion du mois en nom
            noms_mois = [
                "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
            ]
            df_revenus["mois_nom"] = df_revenus["mois"].apply(lambda x: noms_mois[x-1])
            
            # Tri par année et mois
            df_revenus = df_revenus.sort_values(["annee", "mois"])
            
            # Affichage du tableau
            st.subheader("Récapitulatif des revenus")
            
            # Gestion de la compatibilité avec l'ancien format
            if "investissement_disponible_bourse" in df_revenus.columns:
                df_display = df_revenus[["mois_nom", "annee", "montant", "investissement_disponible_bourse", "investissement_disponible_crypto"]].copy()
                df_display["investissement_disponible_bourse"] = df_display["investissement_disponible_bourse"].round().astype(int)
                df_display["investissement_disponible_crypto"] = df_display["investissement_disponible_crypto"].round().astype(int)
                df_display.columns = ["Mois", "Année", "Revenu Net (€)", "Budget Bourse (€)", "Budget Crypto (€)"]
            else:
                df_display = df_revenus[["mois_nom", "annee", "montant", "investissement_disponible"]].copy()
                df_display["investissement_disponible"] = df_display["investissement_disponible"].round().astype(int)
                df_display.columns = ["Mois", "Année", "Revenu Net (€)", "Budget Investissement (€)"]
            st.dataframe(df_display, use_container_width=True)
            
            # Métriques de résumé
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_revenus = df_revenus["montant"].sum()
                st.metric("💰 Total des Revenus", f"{total_revenus:,.0f}€")
            
            with col2:
                total_investissement_bourse = df_revenus.get("investissement_disponible_bourse", df_revenus.get("investissement_disponible", pd.Series([0]))).sum()
                total_investissement_crypto = df_revenus.get("investissement_disponible_crypto", df_revenus.get("investissement_disponible", pd.Series([0]))).sum()
                total_investissement = total_investissement_bourse + total_investissement_crypto
                st.metric("💼 Total Budget Investissement", f"{total_investissement:.2f}€")
            
            with col3:
                nb_mois = len(df_revenus)
                st.metric("📅 Nombre de Mois", f"{nb_mois}")
            
            # Graphique évolution des revenus
            fig_revenus = px.bar(
                df_revenus,
                x="periode",
                y="montant",
                title="Évolution des revenus mensuels",
                labels={"montant": "Revenu Net (€)", "periode": "Période"}
            )
            st.plotly_chart(fig_revenus, use_container_width=True)
            
        else:
            st.info("Aucun revenu enregistré pour le moment")
    
    with tab_overview:
        st.header("📈 Vue d'ensemble")
        
        if data["bourse"] or data["crypto"]:
            # Graphique évolution temporelle
            all_investments = []
            
            for inv in data["bourse"]:
                all_investments.append({
                    "date": inv["date"],
                    "montant": inv["montant"],
                    "type": "Bourse",
                    "symbole": inv["symbole"]
                })
            
            for inv in data["crypto"]:
                all_investments.append({
                    "date": inv["date"],
                    "montant": inv["montant"],
                    "type": "Crypto",
                    "symbole": inv["symbole"]
                })
            
            if all_investments:
                df_all = pd.DataFrame(all_investments)
                df_all["date"] = pd.to_datetime(df_all["date"])
                df_all = df_all.sort_values("date")
                df_all["montant_cumule"] = df_all["montant"].cumsum()
                
                fig_timeline = px.line(
                    df_all,
                    x="date",
                    y="montant_cumule",
                    title="Évolution cumulative des investissements",
                    labels={"montant_cumule": "Montant cumulé (€)", "date": "Date"}
                )
                st.plotly_chart(fig_timeline, use_container_width=True)
                
                # Répartition Bourse vs Crypto
                repartition_data = {
                    "Type": ["Bourse", "Crypto"],
                    "Montant": [budget_utilise_bourse, budget_utilise_crypto]
                }
                
                fig_repartition = px.pie(
                    repartition_data,
                    values="Montant",
                    names="Type",
                    title="Répartition Bourse vs Crypto"
                )
                st.plotly_chart(fig_repartition, use_container_width=True)
        else:
            st.info("Aucun investissement enregistré pour le moment")

if __name__ == "__main__":
    main()