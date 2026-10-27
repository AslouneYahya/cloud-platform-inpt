# INPT Cloud Platform — IaaS & Auth Service

> Plateforme Cloud d'Infrastructure (IaaS) avec système d'authentification sécurisé et module de provisionnement de Machines Virtuelles sur cluster Raspberry Pi (Master / Slaves).

---

## 📸 Aperçu & Captures d'écran

### 1. Authentification Sécurisée (US1)
Page de connexion conforme aux normes **NIST SP 800-63B** et **OWASP ASVS** (Argon2id, anti-énumération, limitation de débit).

![Page de connexion](screenshots/login-page.png)

---

### 2. Tableau de Bord & Suivi des VMs (US2)
Suivi en direct des instances déployées, adresses IP privées, nœuds Raspberry Pi assignés et commandes d'accès SSH.

![Tableau de bord](screenshots/dashboard-view.png)

---

### 3. Formulaire de Déploiement de Machine Virtuelle
Sélection de l'OS (Ubuntu, Debian, Alpine), allocation des ressources (vCPU, RAM, Disque), méthode d'accès (SSH / Mot de passe) et règles de pare-feu.

![Création d'une VM](screenshots/vm-creation-modal.png)

---

### 4. Provisionnement Asynchrone en Cours
Allocation asynchrone sur le cluster avec mécanisme automatique de rollback en cas d'erreur ou ressources insuffisantes.

![Déploiement en cours](screenshots/vm-provisioning.png)

---

### 5. Intégration du Nœud Maître Physique (Raspberry Pi) & Cloudflare Zero Trust (Sprint 2)
Interconnexion sécurisée entre le cluster Raspberry Pi local et le backend Cloud via **Cloudflare Tunnel** et **WARP** (contournement de l'isolation Wi-Fi et pare-feux).

| Tunnel Cloudflare & Réplique Active (ARM64) | Routage Public vers le Listener (`localhost:5000`) |
| :---: | :---: |
| ![Cloudflare Tunnel Overview](screenshots/tunnel.png) | ![Cloudflare Routes](screenshots/cloudflare%20routes.png) |

| Démon `cloudflared` & WARP Actifs sur Raspberry Pi | Mise à jour & Exécution des Scripts du Nœud Maître |
| :---: | :---: |
| ![Statut Cloudflared](screenshots/verifier%20cloudflare%20status%20healthy.jpeg) | ![Exécution Scripts Master Node](screenshots/executing%20scripts%20in%20master%20node.jpeg) |

---

### 6. Contrôle Hardware Réel & Rollback Automatique (Anti-OOM)
Vérification des limites physiques de la Raspberry Pi (`free -m`) avant allocation : en cas de demande excessive (ex: 4 Go demandés alors que seulement 3.25 Go sont disponibles), le déploiement est rejeté avec un message d'erreur explicite et les ressources sont immédiatement libérées.

![Gestion d'erreur et Rollback](screenshots/test-error%20deploiement.png)

---

### 7. Infrastructure Conteneurisée (Docker Desktop)
Les 5 services interconnectés et orchestrés via Docker Compose (Nginx, Backend, Frontend, PostgreSQL, Redis).

| Conteneurs en cours d'exécution | Images Docker construites |
| :---: | :---: |
| ![Conteneurs Docker](screenshots/docker-containers.png) | ![Images Docker](screenshots/docker-images.png) |

---

## 🛠️ Stack Technique

* **Reverse Proxy & TLS :** Nginx Alpine (HTTPS forcé, HSTS, CSP durci)
* **Backend :** Spring Boot 3.3 (Java 21), Spring Security 6, Spring Data JPA
* **Nœud Maître (Cluster Edge) :** Raspberry Pi 4 ARM64, FastAPI (Python 3), Scripts Bash de provisionnement, Systemd
* **Tunnel Sécurisé & Zero Trust :** Cloudflare Tunnel (`cloudflared`), Cloudflare WARP (protocole QUIC / WireGuard)
* **Frontend :** React 18, Vite, React Router, Axios
* **Base de données :** PostgreSQL 16 (Identifiants UUIDv7)
* **Gestion des sessions :** Redis 7 (Sessions distribuées, cookies `HttpOnly`, `Secure`, `SameSite=Lax`)
* **Hachage cryptographique :** Argon2id (`m=65536, t=3, p=1`)
* **Orchestration :** Docker Compose

---

## 🚀 Démarrage Rapide

### 1. Lancer l'infrastructure complète
```bash
docker compose up -d
```
Accéder à l'application : **`https://localhost`**

### 2. Identifiants de Démonstration (pré-remplis)

| Utilisateur | Email | Mot de passe | Statut |
| :--- | :--- | :--- | :--- |
| **Administrateur** | `admin@inpt.ma` | `Admin1234!` | `ACTIVE` |
| **Étudiant (Demo)** | `demo@inpt.ma` | `Admin1234!` | `ACTIVE` |

*(Pour réinitialiser les comptes de test : `docker compose run --rm -e SPRING_PROFILES_ACTIVE=seed backend`)*

---

## 📡 Endpoints API Principaux

| Méthode | Route | Description | Accès |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Création d'un compte utilisateur | Public |
| `POST` | `/api/auth/login` | Authentification & création de session | Public |
| `POST` | `/api/auth/logout` | Révocation immédiate de la session | Session |
| `GET` | `/api/auth/me` | Informations du profil connecté | Session |
| `GET` | `/api/vms` | Liste des VMs de l'utilisateur | Session |
| `POST` | `/api/vms` | Déploiement d'une nouvelle VM | Session |
| `GET` | `/api/vms/{id}` | Détails d'une machine spécifique | Session |
| `POST` | `/api/vms/{id}/start` | Démarrage d'une VM arrêtée | Session |
| `POST` | `/api/vms/{id}/stop` | Arrêt d'une VM active | Session |
| `DELETE`| `/api/vms/{id}` | Destruction et nettoyage des ressources | Session |

---

## 🛡️ Sécurité & Résilience (OWASP & NIST)

* **Argon2id & Temps constant :** Protection contre les attaques temporelles et le cassage de mots de passe.
* **UUIDv7 :** Identifiants temporels non séquentiels empêchant le scraping d'URL.
* **Rate Limiting (Bucket4j) :** Protection contre les attaques par force brute (5 tentatives / min / IP).
* **Isolation Multi-tenant :** Chaque utilisateur ne peut accéder qu'aux VMs dont il est propriétaire.
* **Rollback automatique :** En cas d'erreur de provisionnement ou saturation mémoire, libération immédiate des ressources et marquage `FAILED`.

---

## 🏗️ Cycle de Vie & Cartographie du Déploiement des VMs (Sprint 3)

### 1. Flux d'Exécution & Provisioning de Bout en Bout

```mermaid
sequenceDiagram
    autonumber
    actor User as Développeur / Utilisateur
    participant Front as Frontend (React / Vite)
    participant Nginx as Reverse Proxy (Nginx TLS)
    participant Back as Backend (Spring Boot 3)
    participant DB as PostgreSQL (authdb)
    participant Master as Master Node (FastAPI sur Pi)
    participant Engine as provision.sh (Hardware Pi 4)

    User->>Front: Formulaire création VM (Nom, OS, CPU, RAM, Clé SSH, Ports)
    Front->>Nginx: POST /api/vms
    Nginx->>Back: Proxy vers Spring Boot :8080
    Back->>DB: Sauvegarde entité VM (Statut: PROVISIONING, UUIDv7)
    Back->>DB: Écriture logs AWS-style (VALIDATION, RESOURCE_ALLOCATION)
    Back->>Master: POST https://master.aslouneyahya.com/vms (x-api-key)
    Master->>Engine: bash provision.sh --id ... --name ... --ram ...
    Note over Engine: 1. Contrôle RAM réelle (free -m)<br/>2. Allocation /var/lib/inpt-cloud/vms/{UUID}<br/>3. Attribution IP (192.168.60.x)<br/>4. Init conteneur/VM & pare-feu
    Engine-->>Master: JSON {status: SUCCESS, ip: "192.168.60.x"}
    Master-->>Back: Réponse VmOperationResponse
    Back->>DB: Mise à jour VM (Statut: RUNNING, IP, NodeId)
    Back->>DB: Logs (NETWORK_SETUP, DHCP_LEASE, BOOT_COMPLETE)
    Back-->>Front: Instance créée et active
    Front-->>User: Affichage carte VM, barres de consommation & Console SSH active
```

---

### 2. Cartographie des Fichiers du Système de Déploiement

| Couche | Fichier Source | Rôle Système & Responsabilité |
| :--- | :--- | :--- |
| **1. UI Formulaire** | `frontend/src/components/VmManager.jsx` | Modal de création, validation côté client et affichage des jauges télémétriques temps réel. |
| **2. API Frontend** | `frontend/src/api/vms.js` | Requêtes Axios (`POST /api/vms`, `POST /exec`, `/logs`, `/start`, `/stop`). |
| **3. Proxy & Sécurité** | `nginx/nginx.conf` | Terminaison TLS 1.3, CSP, proxy vers backend et WebSocket upgrade. |
| **4. Contrôleur REST** | `backend/src/main/java/ma/inpt/cloud/vm/VmController.java` | Endpoints sécurisés, validation `@Valid`, gestion des quotas utilisateurs. |
| **5. Orchestrateur Métier** | `backend/src/main/java/ma/inpt/cloud/vm/service/VmService.java` | Génération UUID v7, journalisation AWS CloudWatch (`VmLog`), dispatching au cluster physique. |
| **6. Client Master Node** | `backend/src/main/java/ma/inpt/cloud/vm/client/MasterNodeClient.java` | Client HTTP Spring `RestClient` communiquant avec le Raspberry Pi via Cloudflare Tunnel. |
| **7. Listener API Edge** | `master-node/app/main.py` | API FastAPI sur le Pi recevant les ordres de provisioning, power et exécution Web SSH. |
| **8. Moteur Hardware** | `master-node/scripts/provision.sh` | **Moteur d'orchestration sur le Raspberry Pi** : contrôle des sondes mémoire réelles (`free -m`), création de `/var/lib/inpt-cloud/vms/<ID>/vm.conf`, isolation et pare-feu. |
| **9. Console Web SSH** | `master-node/scripts/exec.sh` | Moteur d'exécution bash directe pour les commandes Web SSH dans le conteneur/hôte. |
| **10. Dashboard Nœud** | `master-node/app/dashboard.py` | Générateur du Dashboard matériel Master Node (`https://master.aslouneyahya.com/dashboard`). |
| **11. Persistance DB** | `backend/src/main/java/ma/inpt/cloud/vm/VirtualMachine.java` | Entité JPA stockant l'état de l'instance, IP, ports, et association utilisateur. |

---

### 3. Emplacement Physique & Commandes d'Accès sur le Raspberry Pi

Sur le Raspberry Pi hôte, chaque instance virtuelle réside dans le système de fichiers local :

```text
/var/lib/inpt-cloud/vms/<VM_UUID>/
└── vm.conf    # Métadonnées : NAME, OS, CPU, RAM_MB, DISK_GB, IP, STATUS
```

#### Accès et administration directe en terminal sur le Pi :
```bash
# 1. Accès direct en SSH à une VM
ssh root@192.168.60.204

# 2. Exécuter une commande dans la VM via l'outil d'exécution local
cd ~/cloud-platform-inpt/master-node/scripts
./exec.sh --id <VM_UUID> --cmd "uname -a"

# 3. Inspecter la configuration de toutes les VMs déployées
cat /var/lib/inpt-cloud/vms/*/vm.conf

# 4. Démarrer ou éteindre une instance manuellement
./power.sh --id <VM_UUID> --action stop
./power.sh --id <VM_UUID> --action start
```

