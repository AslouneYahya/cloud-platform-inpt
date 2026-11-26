# Product Backlog — INPT Cloud Platform (IaaS & Auth Service)

**Projet d'Innovation — Institut National des Postes et Télécommunications (INPT)**  
* **Étudiant :** Yahya ASLOUNE  
* **Encadrantes :** Pr. Safae DAHMANI & Pr. Kaouthar BOUSSELAM  
* **Période :** Année Universitaire 2026/2027  

---

## 📊 Synthèse Globale de l'Avancement des Sprints (Itérations de 1 semaine)

| Sprint | Thématique Principale | Statut | Période / Jalons |
| :---: | :--- | :---: | :---: |
| **Sprint 1** | Socle d'Authentification Sécurisée (NIST/OWASP) & Infrastructure Docker | **Terminé (Checked)** | Semaine 1 |
| **Sprint 2** | Orchestration Edge & Intégration Nœud Maître Physique (Raspberry Pi) | **Terminé (Checked)** | Semaine 2 |
| **Sprint 3** | Télémétrie Matérielle Réelle, Streaming Logs AWS-style & Console Web SSH | **Terminé (Checked)** | Semaine 3 |
| **Sprint 4** | Cluster Multi-Nœuds (Master/Worker) & Virtualisation Matérielle Stricte KVM | **Terminé (Checked)** | Semaine 4 |
| **Sprint 5** | Cluster 100% Décentralisé P2P (`cluster-node`), Synchro Gossip & Haute Disponibilité | **Terminé (Checked)** | Semaine 5 |
| **Sprint 6** | Authentification OAuth2 (Google / GitHub), Session Unifiée & Durcissement Control Plane | **Planifié (À venir)** | Semaine 6 |

---

## 🏁 Sprint 1 — Authentification Sécurisée & Socle Conteneurisé
**Objectif :** Établir une plateforme IaaS robuste, conteneurisée et conforme aux standards de sécurité bancaire et cloud (NIST SP 800-63B & OWASP ASVS).

* [x] **US1.1 : Authentification robuste par mot de passe**
  * Hachage cryptographique **Argon2id** (`m=65536, t=3, p=1`) résistant aux attaques par GPU/FPGA.
  * Validation stricte des mots de passe (longueur, entropie, caractères spéciaux).
* [x] **US1.2 : Gestion de sessions distribuées (Redis 7)**
  * Sessions in-memory centralisées sous Redis découplées du cycle de vie des conteneurs.
  * Cookies sécurisés : drapeaux `HttpOnly`, `Secure`, `SameSite=Lax`.
* [x] **US1.3 : Protection contre la force brute (Rate Limiting)**
  * Limitation de débit via algorithme de Token Bucket (**Bucket4j**) : 5 tentatives max / minute par IP.
* [x] **US1.4 : Protection contre l'énumération d'utilisateurs**
  * Réponses d'authentification uniformes et temps de réponse constant pour masquer l'existence des comptes.
* [x] **US1.5 : Socle d'infrastructure conteneurisé (Docker Compose)**
  * Déploiement multi-services isolé : Nginx (Reverse Proxy TLS), Spring Boot 3.3 (Java 21), React 18 (Vite), PostgreSQL 16, Redis 7.

---

## 🏁 Sprint 2 — Orchestration Edge & Intégration Nœud Maître Physique
**Objectif :** Connecter le Control Plane Cloud à un nœud matériel physique (Raspberry Pi 4 ARM64) via une liaison sécurisée Zero Trust.

* [x] **US2.1 : Interconnexion Zero Trust Cloudflare Tunnel**
  * Tunnel chiffré sortant via `cloudflared` reliant le Raspberry Pi au domaine public `master.aslouneyahya.com`.
  * Élimination complète de l'ouverture de ports entrants sur la box / pare-feu (contournement de l'isolation Wi-Fi universitaire).
* [x] **US2.2 : API d'orchestration Edge (FastAPI)**
  * Démon asynchrone Python sous `systemd` sur le Raspberry Pi pilotant les scripts de provisioning et d'alimentation.
* [x] **US2.3 : Formulaire dynamique de déploiement de VM**
  * Interface React pour spécifier l'OS (Ubuntu, Debian, Alpine), ressources (vCPU, RAM, Disque), clé SSH et règles pare-feu.
* [x] **US2.4 : Contrôle pré-vol hardware & Rollback anti-OOM**
  * Contrôle temps réel de la RAM disponible sur le Pi (`free -m`) avant toute allocation.
  * Rollback automatique et marquage d'erreur explicite en cas de saturation matérielle.
* [x] **US2.5 : Persistance multi-tenant & Identifiants UUIDv7**
  * Modèle relationnel PostgreSQL liant chaque machine virtuelle à son utilisateur propriétaire, avec UUIDv7 temporels non-énumérables.

---

## 🏁 Sprint 3 — Supervision Matérielle Temps Réel, Logs AWS-Style & Web SSH
**Objectif :** Transformer le système en une expérience Cloud complète avec observabilité temps réel et console d'administration interactive.

* [x] **US3.1 : Dashboard de supervision dédié Master Node**
  * Interface web dark-mode accessible sur `https://master.aslouneyahya.com/dashboard` avec rafraîchissement dynamique en direct.
* [x] **US3.2 : Télémétrie matérielle hôte (Sondes physiques du Pi)**
  * Surveillance temps réel de la température du SoC ARM (sonde `/sys` à ~54°C), charge CPU 4 cœurs, RAM physique consommée et stockage SD.
* [x] **US3.3 : Mesure et affichage de la consommation réelle par VM**
  * Intégration de jauges d'utilisation réelle (CPU %, RAM utilisée/allouée, disque utilisé/alloué) avec barres dynamiques alignées strictement 1:1.
  * Affichage synchronisé sur le Dashboard Master Node et sur le portail Web central.
* [x] **US3.4 : Console de streaming des logs en direct (AWS CloudWatch Style)**
  * Streaming temps réel des étapes de cycle de vie (`VALIDATION`, `RESOURCE_ALLOCATION`, `STORAGE_INIT`, `CLOUD_INIT`, `NETWORK_SETUP`, `BOOT_COMPLETE`).
  * Filtrage par sévérité (`INFO`, `WARN`, `ERROR`), auto-scroll et bouton d'export de rapport `.log`.
* [x] **US3.5 : Console Web SSH interactive dans le navigateur**
  * Terminal direct émulant une véritable console SSH (`root@vm:~#`) pour exécuter des commandes en direct sur le nœud ARM64.
* [x] **US3.6 : Cartographie d'architecture & Justifications techniques dans le README**
  * Diagramme de séquence Mermaid de bout en bout, cartographie des 11 fichiers impliqués et justifications argumentées des choix technologiques.

---

## 🏁 Sprint 4 — Cluster Multi-Nœuds (Master/Worker) & Virtualisation Matérielle Stricte KVM
**Objectif :** Étendre l'infrastructure en un véritable cluster distribué multi-nœuds et activer la virtualisation matérielle stricte assistée par le processeur ARM64.

* [x] **US4.1 : Enrôlement Dynamique du Worker Node & Découverte Automatique**
  * Protocole d'auto-enregistrement du Worker Node auprès du Master Node avec battements de cœur périodiques (*Heartbeats*).
  * Auto-détection de l'adresse IP physique LAN (`eth0`/`wlan0`) en ignorant les interfaces virtuelles tunnels (`172.16.x.x`).
* [x] **US4.2 : Contournement de l'AP Isolation via Outbound Tunnel Task Queue**
  * Implémentation d'un patron de file de tâches asynchrone sortante (*Long-Polling*) à travers Cloudflare Tunnel Zero Trust (`/poll` et `/complete`).
  * Permet la communication fiable entre nœuds sur le Wi-Fi universitaire de l'INPT sans requêtes directes LAN ni ports ouverts.
* [x] **US4.3 : Ordonnanceur Intelligent & Équilibrage de Charge (Least-Loaded Scheduler)**
  * Algorithme de placement dynamique choisissant automatiquement le nœud le moins chargé (RAM/CPU) avec option de ciblage explicite d'un nœud.
  * Agrégation multi-nœuds en direct sur le Dashboard Master Node et la console locale.
* [x] **US4.4 : Virtualisation Matérielle Native KVM/QEMU sur ARM64**
  * Exploitation de l'accélération matérielle native `/dev/kvm` via les drapeaux `-enable-kvm -cpu host` de QEMU ARM64.
  * Allocation de disques différentiels virtuels QCOW2 (Copy-on-Write) légers et rapides.
* [x] **US4.5 : Isolation Réseau Virtuelle & Streaming Temps Réel**
  * Isolation réseau par interface virtuelle TAP/virtio-net et attribution dynamique d'adresses IP privées (`10.244.10.x`).
  * Suivi de bout en bout des logs de déploiement en direct et monitoring des instances hébergées sur le Worker.

---

## 🏁 Sprint 5 — Cluster 100% Décentralisé P2P (`cluster-node`) & Haute Disponibilité
**Objectif :** Éliminer totalement le point unique de défaillance (*SPOF*) en transformant le cluster en une topologie homogène Pair-à-Pair (*Peer-to-Peer*) sur les 3 Raspberry Pi 4 physiques avec synchronisation Gossip et bascule Cloudflare Tunnel zéro downtime.

* [x] **US5.1 : Support Multi-Workers Simultanés (Scale-Out Horizontal N > 1)**
  * Capacité d'enrôler dynamiquement plusieurs nœuds simultanés (`worker-01`..`worker-N` / `node-pi-01`..`node-pi-03`) au sein du cluster.
  * Agrégation de la capacité de calcul globale (12 cœurs ARM Cortex-A72, pool RAM 11 382 Mo, stockage flotte) et supervision consolidée.
* [x] **US5.2 : Architecture Décentralisée sans Nœud Fixe (Pool Élastique & Watchdog)**
  * Découplage complet de l'orchestration : élimination de tout adressage statique ou dépendance à un nœud physique unique.
  * File de tâches élastique partagée (*Shared Task Queue*) où tout nœud sain du pool peut revendiquer (*claim*) et exécuter les opérations de provisionnement selon ses ressources libres.
  * Watchdog actif avec basculement automatique (*Auto-failover*) : détection des nœuds bloqués (> 18s) ou hors-ligne (> 25s), réassignation immédiate des tâches dans le pool partagé.
  * Routage dynamique transparent des opérations du cycle de vie des VMs (démarrage, arrêt, suppression KVM) vers le nœud hébergeant l'instance.
* [x] **US5.3 : Unification Peer-to-Peer (`cluster-node`), Synchro Gossip & Failover Cloudflare**
  * Remplacement des rôles asymétriques Master/Worker par un démon universel identique **`PEER`** (`cluster-node/app/main.py`, `mesh.py`, `install_node.sh`) déployé sur chaque Pi.
  * Protocole **Gossip (`merge_peers`)** échangeant les tables de pairs entre répliques Cloudflare pour prévenir le *split-brain*, couplé à un **Garbage Collector distribué (`purge_stale_peers`, TTL 180s)**.
  * Répliques `cloudflared` multiples permettant le basculement automatique sans coupure de `https://master.aslouneyahya.com` lors de l'arrêt d'un Raspberry Pi.
* [x] **US5.4 : Observabilité Hôte Actif, Chaos Testing Matériel & Suite de Tests Unifiée**
  * Mise en évidence dynamique du nœud physique servant la requête (`📍 HÔTE ACTIF` / `PEER (HÔTE)`), validation en conditions réelles sur 3 Raspberry Pi 4 (coupe de `node-pi-01` → bascule immédiate sur `node-pi-03`) et **19/19 tests unitaires** validés.

---

## 🚀 Sprint 6 — Authentification OAuth2 (Google / GitHub), Session Unifiée & Durcissement Control Plane
**Objectif :** Moderniser l'accès utilisateur avec la connexion sociale OAuth2/OIDC (Google et GitHub), unifier la gestion des sessions hybrides (Argon2id + OAuth2) sous Redis 7 et finaliser les outils d'administration entre le Control Plane Spring Boot/React et le cluster P2P.

* [ ] **US6.1 : Authentification Sociale OAuth2 / OIDC avec Google Sign-In**
  * Intégration de `spring-boot-starter-oauth2-client` dans Spring Security 6 pour la connexion via un compte Google (`@inpt.ma` ou personnel).
  * Validation cryptographique des ID Tokens, mapping automatique du profil utilisateur et persistance en base de données PostgreSQL 16 (UUIDv7).
* [ ] **US6.2 : Authentification Sociale OAuth2 avec GitHub Sign-In**
  * Intégration du fournisseur d'identité GitHub OAuth2 pour les profils développeurs et élèves-ingénieurs.
  * Récupération sécurisée des emails vérifiés, gestion des autorisations et conformité stricte aux exigences OWASP ASVS.
* [ ] **US6.3 : Fédération d'Identité Unifiée & Hybridation de Session (Argon2id + OAuth2)**
  * Expérience de connexion unifiée sur le portail Web React (`LoginPage.jsx`) : choix entre l'authentification locale classique (Argon2id + Bucket4j) et la connexion sociale (Google / GitHub en un clic).
  * Synchronisation transparente avec le gestionnaire de sessions distribuées Redis 7 (`spring-session-data-redis`), avec cookies sécurisés et révocation centralisée anti-rejeu.
* [ ] **US6.4 : Finalisation Outillage P2P & Couplage Control Plane**
  * Implémentation de l'endpoint `POST /api/nodes/{node_id}/delete` (avec tombstones Gossip) dans `cluster-node/app/main.py` pour la suppression manuelle immédiate d'un nœud hors-ligne depuis le bouton `🗑️` du dashboard.
  * Remontée de l'adresse IP physique LAN réelle (`eth0`/`wlan0`) dans les heartbeats `cluster-node` au lieu de `127.0.0.1` à travers Cloudflare Tunnel.
  * Vérification et intégration de bout en bout des appels Control Plane Spring Boot (`VmService`) avec le cluster P2P décentralisé.
