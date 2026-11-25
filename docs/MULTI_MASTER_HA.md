# Architecture Haute Disponibilité (HA) & Élection de Leader Multi-Master

**Projet d'Innovation — INPT Rabat**  
* **Étudiant :** Yahya ASLOUNE  
* **Encadrantes :** Pr. Safae DAHMANI & Pr. Kaouthar BOUSSELAM  
* **Module :** High Availability (HA) & Decentralized Control Plane  

---

## 1. Problématique & Objectif

Dans un cluster de virtualisation Edge (sur Raspberry Pi), le **Master Node** constitue traditionnellement un point unique de défaillance (*Single Point of Failure - SPOF*) :
* Si le Master physique est éteint ou déconnecté, les workers ne peuvent plus recevoir d'ordres et l'API de gestion devient inaccessible.
* **Objectif :** Rendre le Master totalement décentralisé et remplaçable grâce à une élection de leader automatique (*Bully/Raft-Jittered Election*) et un basculement transparent sans interruption pour le client.

---

## 2. Architecture & Fonctionnement

```
             Client Web (React) / Backend (Spring Boot)
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
    Cloudflare Edge Load Balancer / Tunnel Replica
    (master.aslouneyahya.com bascule automatiquement)
             │                           │
      ┌──────┴──────┐             ┌──────┴──────┐
      ▼             ▼             ▼             ▼
  [Pi 1 - Master] ◄─── Heartbeat ───► [Pi 2 - Standby Master]
  (Priorité: 100)                     (Priorité: 80)
   - ACTIVE_MASTER                     - STANDBY_WORKER
   - Si Crash / Débranché               - Détecte 3 échecs (9s)
                                       - Backoff de priorité (1.2s)
                                       - S'auto-promeut ACTIVE_MASTER
                                       - Prend le contrôle du cluster
```

### 2.1. Niveaux de Priorité et Élection
Chaque nœud possède une priorité déterministe évitant les conflits (*Split-Brain*) :
* `master-rpi-01` : **Priorité 100** (Master initial par défaut).
* `worker-raspberrypi` : **Priorité 80** (Premier successeur légitime).
* `worker-pi-02` : **Priorité 60** (Deuxième successeur).

### 2.2. Algorithme de Basculement (Failover)
1. **Sonde de surveillance (Watchdog) :** Le worker interroge `GET /health` sur le Master toutes les 3 secondes.
2. **Détection de panne :** Après 3 échecs consécutifs (9s), le Master est déclaré hors service (`DEAD`).
3. **Temporisation par priorité (Jitter Backoff) :**
   $$\text{Délai} = \max(0.2, (100 - \text{Priorité}) \times 0.05)\text{ secondes}$$
   * Worker 1 (Prio 80) attend **1.0 seconde** avant élection.
   * Worker 2 (Prio 60) attend **2.0 secondes**.
4. **Auto-Promotion :** Worker 1 vérifie une dernière fois si un pair a pris la main. Si non, il s'auto-promeut `ACTIVE_MASTER` et démarre le service Master.
5. **Anti Split-Brain :** Quand le délai de Worker 2 expire, il détecte que Worker 1 répond désormais en tant que Master, et abandonne son élection pour rester Worker.

---

## 3. Configuration Cloudflare Tunnel Replicas (Bascule d'URL transparente)

Pour que `https://master.aslouneyahya.com` pointe automatiquement vers le nouveau Master sans modifier la configuration DNS :

Sur **Worker 1 (`worker-raspberrypi`)** et **Worker 2 (`worker-pi-02`)** :
```bash
# Installer cloudflared
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bullseye main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update && sudo apt-get install -y cloudflared

# Enregistrer le service avec le MÊME jeton de tunnel que le Master
sudo cloudflared service install <VOTRE_TUNNEL_TOKEN>
```
Cloudflare achemine automatiquement les requêtes vers le nœud qui a son port 5000 actif !

---

## 4. Endpoints de Télémétrie HA

* **`GET /api/cluster/ha` (Master Node)** :
  ```json
  {
    "status": "SUCCESS",
    "ha": {
      "node_id": "master-rpi-01",
      "role": "MASTER",
      "priority": 100,
      "active_leader": "master-rpi-01",
      "is_leader": true,
      "master_healthy": true,
      "consecutive_failures": 0
    }
  }
  ```
* **`GET /ha` (Worker Node Agent)** :
  Rapporte l'état de la sonde de surveillance du worker et son état de veille.
