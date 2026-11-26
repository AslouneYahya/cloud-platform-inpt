# INPT Cloud Platform — Sprint 5 : Captures & Démonstration du Cluster P2P Décentralisé

> **Projet d'Innovation — Institut National des Postes et Télécommunications (INPT, Rabat)**  
> **Étudiant :** Yahya ASLOUNE | **Encadrantes :** Pr. Safae DAHMANI & Pr. Kaouthar BOUSSELAM  
> **Rapport complet :** Voir [`SPRINT5_README.md`](../../SPRINT5_README.md)

---

## 📸 Galerie de Preuves Réelles sur Cluster Raspberry Pi 4 (3 Nœuds Pairs)

Les 2 captures ci-dessous documentent la migration complète vers l'architecture **100% décentralisée Pair-à-Pair (`cluster-node`)** et valident le basculement automatique sans coupure sur le domaine public **`https://master.aslouneyahya.com/dashboard`**.

---

### Capture 1 : Flotte P2P Complète — 3 / 3 Raspberry Pi Pairs en Ligne

![Dashboard P2P avec les 3 nœuds en ligne](<dashboard will all nodes online.png>)

* **Fichier :** [`dashboard will all nodes online.png`](<dashboard will all nodes online.png>)
* **Nœud répondant au domaine :** `📍 Hôte Actuel : node-pi-01 • HEALTHY` (`PEER (HÔTE)` avec bordure lumineuse émeraude, Uptime `up 4 hours, 10 minutes`).
* **Pool consolidé du cluster :**
  * **12 Cœurs vCPU** (`ARM Cortex-A72`)
  * **11382 Mo RAM Pool** (`3010 Mo consommés`, `26%`)
  * **57.6 Go Stockage** (`23.1 Go libres`, `59%`)
  * **3 / 3 Nœuds Pairs Actifs** (`node-pi-01` à 60.4°C / 0 VM, `node-pi-03` à 56.0°C / 1 VM KVM, `node-pi-02` à 56.5°C / 1 VM KVM).

---

### Capture 2 : Basculement Haute Disponibilité après Arrêt de Node 1 (Zéro Downtime)

![Dashboard après arrêt de Node 1](<dashboard after stopping node 1.png>)

* **Fichier :** [`dashboard after stopping node 1.png`](<dashboard after stopping node 1.png>)
* **Test effectué :** Coupure du nœud **`node-pi-01`** et rafraîchissement direct de **`https://master.aslouneyahya.com/dashboard`**.
* **Résultat vérifié :**
  * Le domaine public reste **100% accessible sans interruption** : Cloudflare Tunnel Edge bascule instantanément vers la réplique **`node-pi-03`**, qui devient **`📍 Hôte Actuel : node-pi-03 • HEALTHY`** (`PEER (HÔTE)`, 57.0°C, Charge `0.36`, RAM `792 / 3794 Mo`).
  * **`node-pi-01`** passe proprement en statut **`OFFLINE`** (`0%` RAM).
  * La flotte affiche **`2 / 3 Nœuds Pairs Actifs`** (`1849 Mo consommés`, `16%`) et toutes les VMs KVM restantes continuent de tourner normalement.
