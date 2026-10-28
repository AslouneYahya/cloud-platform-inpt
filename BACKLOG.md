# Product Backlog — INPT Cloud Platform (IaaS & Auth Service)

**Projet d'Innovation — Institut National des Postes et Télécommunications (INPT)**  
* **Étudiant :** Yahya ASLOUNE  
* **Encadrante :** Pr. Safae DAHMANI  
* **Période :** Année Universitaire 2026  

---

## 📊 Synthèse Globale de l'Avancement des Sprints (Itérations de 1 semaine)

| Sprint | Thématique Principale | Statut | Période / Jalons |
| :---: | :--- | :---: | :---: |
| **Sprint 1** | Socle d'Authentification Sécurisée (NIST/OWASP) & Infrastructure Docker | **Terminé (Checked)** | Semaine 1 |
| **Sprint 2** | Orchestration Edge & Intégration Nœud Maître Physique (Raspberry Pi) | **Terminé (Checked)** | Semaine 2 |
| **Sprint 3** | Télémétrie Matérielle Réelle, Streaming Logs AWS-style & Console Web SSH | **Terminé (Checked)** | Semaine 3 |
| **Sprint 4** | Cluster Multi-Nœuds (Master/Slaves) & Virtualisation Matérielle Stricte KVM | **Planifié (En cours)** | Semaine 4 |

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

## 🚀 Sprint 4 — Cluster Multi-Nœuds (Master/Slaves) & Virtualisation Matérielle Stricte KVM
**Objectif :** Étendre l'infrastructure en un véritable cluster distribué multi-nœuds et activer la virtualisation matérielle stricte assistée par le processeur.

* [ ] **US4.1 : Interconnexion et Enrôlement des Nœuds Esclaves (Worker / Slave Nodes)**
  * Protocole de communication et d'enregistrement des nœuds workers auprès du Nœud Maître.
  * Découverte automatique et synchronisation d'état du cluster distribué.
* [ ] **US4.2 : Moteur d'Ordonnancement et d'Équilibrage de Charge (Cluster Scheduler)**
  * Algorithme de placement intelligent des VMs sur le nœud le plus adapté selon la disponibilité RAM/CPU.
  * Visualisation globale de la topologie du cluster sur le Dashboard.
* [ ] **US4.3 : Virtualisation Matérielle Stricte KVM/QEMU (ARM64)**
  * Exploitation de l'accélération matérielle `/dev/kvm` native du processeur ARM Cortex-A72.
  * Instanciation de véritables machines virtuelles indépendantes à partir d'images officielles Cloud-Init (`.qcow2`).
* [ ] **US4.4 : Isolation Réseau Complète via Ponts Virtuels (Bridge & virtio-net)**
  * Création d'interfaces réseau virtuelles isolées (`veth` / TAP) et sous-réseau étanche (`netns`) pour chaque VM.
  * Étanchéité réseau stricte lors de l'exécution de commandes réseau (`ip addr`, routage dédié).
* [ ] **US4.5 : Haute Disponibilité et Tolérance aux Pannes (Heartbeat & Failover)**
  * Mécanisme de battement de cœur (*heartbeat*) pour surveiller l'état de santé de chaque nœud du cluster.
  * Réallocation automatique des instances en cas de déconnexion imprévue d'un Worker Node.
