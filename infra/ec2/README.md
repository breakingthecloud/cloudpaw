# CloudPaw ops EC2 (centro de operaciones)

Una sola máquina en AWS con todo el stack, para no instalarlo en las laptops: ROS 2 Jazzy + Gazebo + ros2_control,
foxglove_bridge, MuJoCo / strands-robots (con uv), Node 22 + pnpm + CLI de AgentCore, AWS CLI.

Los IDs y el perfil de **tu** despliegue van en `infra/ec2/ops.local.env` (copia `ops.local.env.example`; ese archivo no se sube a git):

```bash
source infra/ec2/ops.local.env
```

| Recurso | Valor |
|---|---|
| Instancia | `$CLOUDPAW_INSTANCE_ID` (`cloudpaw-ops`), m7i.xlarge: 4 vCPU, 16 GiB, x86_64 |
| Sistema | Ubuntu 24.04 LTS (AMI oficial de Canonical: parámetro SSM `/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id`) |
| Disco | gp3 60 GB, cifrado, se borra con la instancia |
| Red | VPC por defecto, `us-east-1a`; security group `$CLOUDPAW_SG_ID` (`cloudpaw-ops`) **sin reglas de entrada** |
| Acceso | Solo SSM Session Manager; IMDSv2 obligatorio (IMDSv1 da 401) |
| Rol | `cloudpaw-ops-ec2`: `AmazonSSMManagedInstanceCore` + `bedrock-invoke` (solo `InvokeModel*`; ver `bedrock-invoke.json`) |
| Auto-apagado | Alarma `cloudpaw-ops-idle-stop`: CPU < 5% durante 1 h → **stop** (no terminate) |
| Etiquetas | `Project=cloudpaw` en instancia, disco, SG, rol y alarma |

## Costo (on-demand us-east-1, 17-nov-2026)

$0.2016/h de cómputo solo mientras está encendida (~$35/mes con 8 h × 22 días; ~$147/mes 24×7) + disco gp3 60 GB ~$4.8/mes
**aunque esté apagada**. Apágala al terminar: `aws ec2 stop-instances --instance-ids $CLOUDPAW_INSTANCE_ID --profile $CLOUDPAW_PROFILE`.

## Conectarse

Necesitas el plugin de Session Manager en tu Mac (`brew install --cask session-manager-plugin`).

```bash
aws sso login --profile $CLOUDPAW_PROFILE
aws ec2 start-instances --instance-ids $CLOUDPAW_INSTANCE_ID --profile $CLOUDPAW_PROFILE --region us-east-1   # si está apagada
aws ssm start-session --target $CLOUDPAW_INSTANCE_ID --profile $CLOUDPAW_PROFILE --region us-east-1
sudo -iu ubuntu            # la sesión entra como ssm-user; el entorno está en el usuario ubuntu
```

Ver la simulación de ROS en el navegador (Foxglove), sin abrir puertos: túnel SSM al puerto 8765.
```bash
aws ssm start-session --target $CLOUDPAW_INSTANCE_ID --profile $CLOUDPAW_PROFILE --region us-east-1 \
  --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["8765"],"localPortNumber":["8765"]}'
# en la instancia: ros2 launch foxglove_bridge foxglove_bridge_launch.xml
# en tu navegador: Foxglove → Open connection → ws://localhost:8765
```

## Instalación

`bootstrap.sh` es idempotente; se puede volver a correr. Log en `/var/log/cloudpaw-bootstrap.log`; al terminar escribe las
versiones en `/var/lib/cloudpaw/bootstrap.done`. El entorno del usuario `ubuntu` está en `~/.cloudpaw_env` (lo carga `.bashrc`).

## Borrar todo

```bash
P="--profile $CLOUDPAW_PROFILE --region $AWS_REGION"
aws ec2 terminate-instances --instance-ids $CLOUDPAW_INSTANCE_ID $P && aws ec2 wait instance-terminated --instance-ids $CLOUDPAW_INSTANCE_ID $P
aws cloudwatch delete-alarms --alarm-names cloudpaw-ops-idle-stop $P
aws ec2 delete-security-group --group-id $CLOUDPAW_SG_ID $P
aws iam remove-role-from-instance-profile --instance-profile-name cloudpaw-ops-ec2 --role-name cloudpaw-ops-ec2 $P
aws iam delete-instance-profile --instance-profile-name cloudpaw-ops-ec2 $P
aws iam detach-role-policy --role-name cloudpaw-ops-ec2 --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore $P
aws iam delete-role-policy --role-name cloudpaw-ops-ec2 --policy-name bedrock-invoke $P
aws iam delete-role --role-name cloudpaw-ops-ec2 $P
```
