"""
Logique métier de l'application d'investissement
"""

import math
from typing import Dict, List, Tuple


def calculer_investissements_automatiques(revenu_net: float) -> Tuple[float, float]:
    """
    Calcule automatiquement les montants d'investissement bourse et crypto

    Args:
        revenu_net: Montant du revenu net mensuel

    Returns:
        Tuple (investissement_bourse, investissement_crypto)
    """
    montant_investissement_bourse = round(revenu_net * 0.10, 2)
    montant_investissement_crypto = round(revenu_net * 0.10, 2)
    return montant_investissement_bourse, montant_investissement_crypto


def verifier_periode_existante(revenus: List[Dict], periode: str) -> bool:
    """
    Vérifie si une période existe déjà dans les revenus

    Args:
        revenus: Liste des revenus existants
        periode: Période à vérifier (format "YYYY-MM")

    Returns:
        True si la période existe déjà, False sinon
    """
    return any(r["periode"] == periode for r in revenus)


def creer_periode(annee: int, mois: int) -> str:
    """
    Crée une chaîne de période au format YYYY-MM

    Args:
        annee: Année
        mois: Mois (1-12)

    Returns:
        Période formatée
    """
    return f"{annee}-{mois:02d}"


def calculer_quantite_investissement(montant: float, prix_unitaire: float) -> float:
    """
    Calcule la quantité d'un investissement

    Args:
        montant: Montant investi
        prix_unitaire: Prix unitaire de l'actif

    Returns:
        Quantité calculée
    """
    if prix_unitaire <= 0:
        raise ValueError("Le prix unitaire doit être supérieur à 0")
    return montant / prix_unitaire


def calculer_budget_disponible(revenus: List[Dict]) -> Tuple[int, int, int]:
    """
    Calcule les budgets disponibles pour les investissements

    Args:
        revenus: Liste des revenus

    Returns:
        Tuple (budget_bourse, budget_crypto, budget_total)
    """
    budget_bourse_brut = sum([r["investissement_disponible_bourse"] for r in revenus])
    budget_crypto_brut = sum([r["investissement_disponible_crypto"] for r in revenus])

    budget_bourse = math.ceil(budget_bourse_brut)
    budget_crypto = math.ceil(budget_crypto_brut)
    budget_total = budget_bourse + budget_crypto

    return budget_bourse, budget_crypto, budget_total


def calculer_budget_utilise(investissements: List[Dict]) -> Tuple[float, float]:
    """
    Calcule le budget utilisé (hors investissements hors budget)

    Args:
        investissements: Liste des investissements

    Returns:
        Tuple (budget_utilise, total_investi)
    """
    budget_utilise = sum([i["montant"] for i in investissements if not i.get("hors_budget", False)])
    total_investi = sum([i["montant"] for i in investissements])

    return budget_utilise, total_investi


def calculer_budget_restant(budget_disponible: float, budget_utilise: float) -> float:
    """
    Calcule le budget restant

    Args:
        budget_disponible: Budget total disponible
        budget_utilise: Budget déjà utilisé

    Returns:
        Budget restant
    """
    return budget_disponible - budget_utilise


def valider_donnees_revenu(revenu_net: float, mois: int, annee: int) -> List[str]:
    """
    Valide les données d'un revenu

    Args:
        revenu_net: Montant du revenu net
        mois: Mois (1-12)
        annee: Année

    Returns:
        Liste des erreurs de validation (vide si valide)
    """
    erreurs = []

    if revenu_net <= 0:
        erreurs.append("Le revenu net doit être supérieur à 0")

    if mois < 1 or mois > 12:
        erreurs.append("Le mois doit être entre 1 et 12")

    if annee < 2020 or annee > 2030:
        erreurs.append("L'année doit être entre 2020 et 2030")

    return erreurs


def valider_donnees_investissement(montant: float, prix_unitaire: float, symbole: str) -> List[str]:
    """
    Valide les données d'un investissement

    Args:
        montant: Montant de l'investissement
        prix_unitaire: Prix unitaire
        symbole: Symbole de l'actif

    Returns:
        Liste des erreurs de validation (vide si valide)
    """
    erreurs = []

    if montant <= 0:
        erreurs.append("Le montant doit être supérieur à 0")

    if prix_unitaire <= 0:
        erreurs.append("Le prix unitaire doit être supérieur à 0")

    if not symbole or not symbole.strip():
        erreurs.append("Le symbole est obligatoire")

    return erreurs


def creer_donnees_revenu(mois: int, annee: int, montant: float) -> Dict:
    """
    Crée un dictionnaire de données pour un revenu

    Args:
        mois: Mois
        annee: Année
        montant: Montant du revenu

    Returns:
        Dictionnaire des données du revenu
    """
    periode = creer_periode(annee, mois)
    inv_bourse, inv_crypto = calculer_investissements_automatiques(montant)

    return {
        "mois": mois,
        "annee": int(annee),
        "periode": periode,
        "montant": montant,
        "investissement_disponible_bourse": inv_bourse,
        "investissement_disponible_crypto": inv_crypto,
    }


def creer_donnees_investissement(
    date_achat: str, symbole: str, montant: float, prix_unitaire: float, hors_budget: bool = False
) -> Dict:
    """
    Crée un dictionnaire de données pour un investissement

    Args:
        date_achat: Date d'achat (format ISO)
        symbole: Symbole de l'actif
        montant: Montant investi
        prix_unitaire: Prix unitaire
        hors_budget: Si l'investissement est hors budget

    Returns:
        Dictionnaire des données de l'investissement
    """
    quantite = calculer_quantite_investissement(montant, prix_unitaire)

    return {
        "date": date_achat,
        "symbole": symbole.upper(),
        "montant": montant,
        "prix_unitaire": prix_unitaire,
        "quantite": quantite,
        "hors_budget": hors_budget,
    }


def valider_donnees_vente(
    montant: float,
    prix_unitaire: float,
    symbole: str,
    quantite_vente: float,
    investissements: List[Dict],
) -> List[str]:
    """
    Valide les données d'une vente

    Args:
        montant: Montant de la vente
        prix_unitaire: Prix unitaire de vente
        symbole: Symbole de l'actif
        quantite_vente: Quantité à vendre
        investissements: Liste des investissements existants pour ce symbole

    Returns:
        Liste des erreurs de validation (vide si valide)
    """
    erreurs = []

    if montant <= 0:
        erreurs.append("Le montant de vente doit être supérieur à 0")

    if prix_unitaire <= 0:
        erreurs.append("Le prix unitaire de vente doit être supérieur à 0")

    if quantite_vente <= 0:
        erreurs.append("La quantité à vendre doit être supérieure à 0")

    if not symbole or not symbole.strip():
        erreurs.append("Le symbole est obligatoire")

    # Vérifier la quantité disponible
    quantite_disponible = calculer_quantite_disponible(investissements, symbole)
    if quantite_vente > quantite_disponible:
        erreurs.append(
            f"Quantité insuffisante. Disponible: {quantite_disponible:.4f}, demandée: {quantite_vente:.4f}"
        )

    return erreurs


def calculer_quantite_disponible(investissements: List[Dict], symbole: str) -> float:
    """
    Calcule la quantité disponible pour un symbole donné
    (somme des achats - somme des ventes)

    Args:
        investissements: Liste de tous les investissements
        symbole: Symbole de l'actif

    Returns:
        Quantité disponible pour vente
    """
    quantite_totale = 0.0

    for inv in investissements:
        if inv["symbole"].upper() == symbole.upper():
            # Les achats ont une quantité positive, les ventes négative
            if inv.get("type_operation") == "Vente":
                quantite_totale -= inv["quantite"]  # Soustraire les ventes
            else:
                quantite_totale += inv["quantite"]  # Ajouter les achats

    return max(0.0, quantite_totale)  # Ne pas retourner de quantité négative


def verifier_position_suffisante(
    investissements: List[Dict], symbole: str, quantite_demandee: float
) -> bool:
    """
    Vérifie si on a suffisamment de quantité pour effectuer une vente

    Args:
        investissements: Liste des investissements
        symbole: Symbole de l'actif
        quantite_demandee: Quantité qu'on veut vendre

    Returns:
        True si la position est suffisante
    """
    quantite_disponible = calculer_quantite_disponible(investissements, symbole)
    return quantite_demandee <= quantite_disponible


def creer_donnees_vente(
    date_vente: str,
    symbole: str,
    montant: float,
    prix_unitaire: float,
    type_operation: str = "Vente",
) -> Dict:
    """
    Crée un dictionnaire de données pour une vente
    Note: La quantité sera stockée comme positive, mais sera traitée comme négative dans les calculs

    Args:
        date_vente: Date de vente (format ISO)
        symbole: Symbole de l'actif
        montant: Montant de la vente (positif)
        prix_unitaire: Prix unitaire de vente
        type_operation: Type d'opération (toujours "Vente")

    Returns:
        Dictionnaire des données de la vente
    """
    quantite = calculer_quantite_investissement(montant, prix_unitaire)

    return {
        "date": date_vente,
        "symbole": symbole.upper(),
        "montant": montant,  # Montant positif pour l'affichage
        "prix_unitaire": prix_unitaire,
        "quantite": quantite,  # Quantité positive pour l'affichage, gérée comme négative dans les calculs
        "hors_budget": True,  # Les ventes sont toujours hors budget (ne consomment pas le budget)
        "type_operation": type_operation,
    }


def calculer_positions_restantes_fifo(investissements: List[Dict], symbole: str) -> List[Dict]:
    """
    Calcule les positions restantes par ligne d'achat après application FIFO des ventes

    Args:
        investissements: Liste de tous les investissements
        symbole: Symbole de l'actif

    Returns:
        Liste des achats avec quantités restantes après ventes FIFO
    """
    # Filtrer et trier par date (FIFO = First In, First Out)
    symbol_investments = [
        inv for inv in investissements if inv["symbole"].upper() == symbole.upper()
    ]

    # Trier par date pour FIFO
    symbol_investments.sort(key=lambda x: x["date"])

    # Séparer achats et ventes
    purchases = [inv for inv in symbol_investments if inv.get("type_operation") != "Vente"]
    sales = [inv for inv in symbol_investments if inv.get("type_operation") == "Vente"]

    # Créer une copie des achats avec quantité restante
    remaining_positions = []
    for purchase in purchases:
        remaining_positions.append(
            {
                "date": purchase["date"],
                "type_operation": purchase.get("type_operation", "Achat"),
                "prix_unitaire": purchase["prix_unitaire"],
                "quantite_initiale": purchase["quantite"],
                "quantite_restante": purchase["quantite"],
                "montant_initial": purchase["montant"],
                "montant_restant": purchase["montant"],
            }
        )

    # Appliquer les ventes FIFO
    for sale in sales:
        quantity_to_sell = sale["quantite"]

        # Appliquer la vente sur les positions restantes (FIFO)
        for position in remaining_positions:
            if quantity_to_sell <= 0:
                break

            if position["quantite_restante"] > 0:
                # Calculer combien on peut vendre de cette position
                qty_from_this_position = min(position["quantite_restante"], quantity_to_sell)

                # Mettre à jour la position
                position["quantite_restante"] -= qty_from_this_position
                position["montant_restant"] = (
                    position["quantite_restante"] * position["prix_unitaire"]
                )

                # Réduire la quantité à vendre
                quantity_to_sell -= qty_from_this_position

    # Filtrer pour ne garder que les positions avec des informations utiles
    return [pos for pos in remaining_positions if pos["quantite_initiale"] > 0]
