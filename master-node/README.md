# INPT Cloud Platform — Master Node (Raspberry Pi)

Ce dossier contient le service d'écoute (**Listener**) et le moteur d'exécution de scripts du **Nœud Maître (Master Node)** destiné à être exécuté sur la Raspberry Pi.

---

## 🏗️ Architecture & Fonctionnement

```
[ Interface Web / Spring Boot ]
             │
             │ HTTP REST (JSON)
             │ Header: X-Cluster-Token: inpt-cluster-secret-2026
             ▼
[ Listener FastAPI (Port 5000) ] ── (Python Daemon sur Raspberry Pi)
             │
             ├── 1. Validation du schéma JSON (Pydantic)
             ├── 2. Vérification de la capacité (RAM, CPU, Disque)
             └── 3. Traduction & Exécution du Script Shell :
                     │
                     ├── scripts/provision.sh   (Création, IP DHCP, SSH, Pare-feu)
                     ├── scripts/deprovision.sh (Nettoyage & Rollback)
                     ├── scripts/power.sh       (Démarrage / Arrêt)
                     └── scripts/check_health.sh (Télémétrie hardware)
```

---

## 🌐 Contournement Réseau & Tunnel Cloudflare (Wi-Fi Campus / 4G)

Si la Raspberry Pi se trouve sur un réseau Wi-Fi avec isolation de clients (AP Isolation) ou pare-feux stricts :

```bash
chmod +x setup_cloudflare_tunnel.sh
./setup_cloudflare_tunnel.sh
```
Ce script :
- Détecte l'architecture ARM (32 ou 64-bit) de la Pi.
- Installe le binaire officiel `cloudflared`.
- Configure un service `systemd` résilient en mode **HTTP/2 (TCP port 443)**.
- Établit un tunnel sécurisé direct vers Cloudflare Zero Trust.

---

## 🚀 Installation sur la Raspberry Pi (en 3 étapes)

### 1. Copier le dossier sur la Raspberry Pi
Depuis votre PC (remplacer `192.168.1.50` par l'IP de votre Pi) :
```bash
scp -r "master-node" pi@192.168.1.50:~/master-node
```

### 2. Se connecter en SSH à la Raspberry Pi
```bash
ssh pi@192.168.1.50
cd ~/master-node
```

### 3. Lancer l'installation automatique
```bash
chmod +x install.sh
./install.sh
```
Ce script installe les dépendances Python, configure les permissions d'exécution des scripts Bash et active le démon en tant que service système `systemd` (`inpt-master-node.service`).

---

## 🧪 Tests du Listener (depuis la Pi ou votre PC)

### 1. Vérifier la santé du Nœud Maître
```bash
curl -i http://localhost:5000/health
```
Réponse attendue :
```json
{
  "node_name": "raspberrypi",
  "status": "HEALTHY",
  "cpu_cores": 4,
  "ram_used_mb": 420,
  "ram_total_mb": 3840,
  "disk_free_gb": 24.5,
  "active_vms": 0
}
```

### 2. Tester le provisionnement d'une VM via API
```bash
curl -i -X POST http://localhost:5000/vms \
  -H "Content-Type: application/json" \
  -H "X-Cluster-Token: inpt-cluster-secret-2026" \
  -d '{
    "vm_id": "01a12fcb-4072-79a9-8418-80cb45e99f4e",
    "name": "test-vm-rpi",
    "os": "Ubuntu 22.04 LTS",
    "cpu": 2,
    "ram_mb": 1024,
    "disk_gb": 20,
    "open_ports": [22, 80]
  }'
```

---

## ⚙️ Commandes Utiles de Supervision sur la Pi

* Voir le statut du service : `sudo systemctl status inpt-master-node.service`
* Consulter les logs en temps réel : `sudo journalctl -u inpt-master-node.service -f`
* Redémarrer le service : `sudo systemctl restart inpt-master-node.service`
