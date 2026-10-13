"""Generates the Company Inc. HLD as both a draw.io file and an SVG from one layout definition.

Usage: python3 docs/src/hld.py   (writes docs/company-inc-hld.drawio and docs/company-inc-hld.svg)
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent
W, H = 1400, 900

# Palette: (stroke, fill, text)
C = {
    "org": ("#5A6B86", "#F4F6F9", "#2E3A4E"),
    "acct": ("#C7166F", "#FFFFFF", "#8C0F4E"),
    "vpc": ("#248814", "#FFFFFF", "#1C6B10"),
    "pub": ("#7AA116", "#F2F8E6", "#4B6A0A"),
    "priv": ("#147EBA", "#EAF4FB", "#0E5A86"),
    "eks": ("#ED7100", "#FFF6EC", "#A34D00"),
    "data": ("#00684A", "#E9F7F1", "#00684A"),
    "ops": ("#7B5CD6", "#F5F2FD", "#4E37A0"),
    "cicd": ("#2E3A4E", "#F4F6F9", "#2E3A4E"),
    "node": ("#5A6B86", "#FFFFFF", "#1B2333"),
}

# (id, label, x, y, w, h, palette, is_container)
shapes = []
def group(i, label, x, y, w, h, pal): shapes.append((i, label, x, y, w, h, pal, True))
def node(i, label, x, y, w, h, pal="node"): shapes.append((i, label, x, y, w, h, pal, False))

# AWS Organization
group("org", "AWS Organization · Control Tower · SCPs · IAM Identity Center", 20, 16, 1360, 96, "org")
for k, (i, lbl) in enumerate([
    ("a_mgmt", "Management\nbilling · SSO"), ("a_log", "Log Archive\nCloudTrail · Config"),
    ("a_sec", "Security\nGuardDuty · Sec Hub"), ("a_shared", "Shared Services\nECR · Route 53 · CI roles"),
    ("a_dev", "Dev\nEKS · Atlas Flex"), ("a_stg", "Staging\nprod-like, smaller"), ("a_prod", "Prod\ndetailed below"),
]):
    node(i, lbl, 34 + k * 192, 46, 178, 54, "acct" if i == "a_prod" else "node")

# Edge / entry
node("users", "Users\n(browser)", 30, 150, 170, 52)
node("r53", "Route 53\nDNS · health checks", 30, 240, 170, 52)
node("cf", "CloudFront + AWS WAF\nShield Std · ACM TLS", 30, 330, 170, 60)
node("s3", "S3 (private, OAC)\nReact SPA bundle", 30, 470, 170, 56)

# Prod account / VPC
group("prod", "Prod account · eu-central-1", 230, 136, 850, 570, "acct")
group("vpc", "VPC 10.0.0.0/16 · 3 Availability Zones · Flow Logs", 248, 166, 814, 524, "vpc")
group("pub", "Public subnets ×3", 266, 194, 778, 78, "pub")
node("alb", "Application Load Balancer\nAWS LB Controller · TLS", 365, 214, 230, 48)
node("nat", "NAT Gateway (per AZ)\negress only", 800, 214, 226, 48)

group("app", "Private app subnets ×3 (no public IPs)", 266, 286, 778, 280, "priv")
group("eks", "Amazon EKS (private API endpoint) · Pod Security 'restricted' · NetworkPolicies", 280, 314, 750, 240, "eks")
node("api", "api Deployment (Flask/gunicorn)\nHPA 3→50 · PDB · topology spread", 310, 346, 340, 50)
node("argocd", "Argo CD + Argo Rollouts\nGitOps sync · canary", 666, 346, 348, 50)
node("ng_sys", "System managed node group\non-demand · Bottlerocket · 3 AZ\nCoreDNS · Karpenter · Argo CD", 310, 410, 224, 70)
node("ng_kp", "Karpenter NodePools\nGraviton · Spot + On-Demand\nscale 0 → N on demand", 550, 410, 224, 70)
node("ops_k8s", "Platform add-ons\nExternal Secrets · ADOT\nFluent Bit · Kyverno", 790, 410, 224, 70)
node("vpa", "VPA (recommend mode) · ResourceQuota · LimitRange per namespace", 310, 494, 704, 38)

group("datas", "Private data subnets ×3", 266, 580, 778, 96, "priv")
node("pl", "PrivateLink endpoint\n→ MongoDB Atlas", 310, 604, 230, 52)
node("vpce", "VPC endpoints\nECR · S3 · STS · Secrets Manager · KMS", 556, 604, 458, 52)

# MongoDB Atlas
group("atlas", "MongoDB Atlas (AWS, same region)", 1110, 400, 270, 250, "data")
node("m1", "Primary · AZ-a", 1126, 432, 238, 34)
node("m2", "Secondary · AZ-b", 1126, 474, 238, 34)
node("m3", "Secondary · AZ-c", 1126, 516, 238, 34)
node("bkp", "Cloud Backup: continuous PITR\n+ snapshots copied to eu-west-1\nKMS BYOK encryption", 1126, 566, 238, 70)

# Security & ops services
group("sops", "Security & observability", 1110, 136, 270, 246, "ops")
node("kms", "AWS KMS (CMKs)", 1126, 166, 238, 32)
node("sm", "Secrets Manager", 1126, 206, 238, 32)
node("obs", "Managed Prometheus · Grafana\nCloudWatch Logs · X-Ray", 1126, 246, 238, 48)
node("sec", "GuardDuty (EKS) · Security Hub\nCloudTrail · IAM Access Analyzer", 1126, 302, 238, 48)

# CI/CD
group("cicd", "CI/CD · trunk-based · merge → dev, PR promotion → staging/prod", 20, 726, 1360, 156, "cicd")
node("gh", "GitHub\napp repos · PR review", 40, 776, 170, 60)
node("gha", "GitHub Actions (OIDC → AWS)\ntests · lint · SAST · Trivy\nbuild · SBOM · cosign sign", 260, 768, 250, 76)
node("ecr", "Amazon ECR (Shared Services)\nimmutable tags · scan on push\nlifecycle · cross-account pull", 560, 768, 250, 76)
node("gitops", "GitOps repo\nHelm charts + per-env values\nimage tag bump by CI", 860, 768, 230, 76)
node("tf", "Terraform + Atlantis\nAWS, EKS, Atlas providers", 1140, 776, 220, 60)

# Edges: (src, dst, label, waypoints)
edges = [
    ("users", "r53", "", [(115, 202), (115, 240)]),
    ("r53", "cf", "", [(115, 292), (115, 330)]),
    ("cf", "s3", "/*", [(115, 390), (115, 470)]),
    ("cf", "alb", "/api/*", [(200, 360), (215, 360), (215, 238), (365, 238)]),
    ("alb", "api", "", [(480, 262), (480, 346)]),
    ("api", "pl", "", [(310, 371), (294, 371), (294, 630), (310, 630)]),
    ("pl", "m1", "TLS · private", [(425, 656), (425, 698), (1090, 698), (1090, 449), (1126, 449)]),
    ("gh", "gha", "", [(210, 806), (260, 806)]),
    ("gha", "ecr", "push", [(510, 806), (560, 806)]),
    ("gha", "gitops", "PR", [(385, 844), (385, 862), (975, 862), (975, 844)]),
    ("gitops", "argocd", "pull", [(975, 768), (975, 716), (1046, 716), (1046, 371), (1014, 371)]),
    ("gha", "s3", "SPA deploy", [(290, 768), (290, 756), (215, 756), (215, 498), (200, 498)]),
    ("ops_k8s", "sm", "", [(1014, 445), (1070, 445), (1070, 222), (1126, 222)]),
]

by_id = {s[0]: s for s in shapes}

def edge_points(src, dst, pts):
    return pts

# ---------------- SVG ----------------
def svg():
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           'font-family="Helvetica, Arial, sans-serif">',
           '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#2E3A4E"/></marker></defs>',
           f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>']
    for i, label, x, y, w, h, pal, cont in shapes:
        stroke, fill, text = C[pal]
        if cont:
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" '
                       f'stroke-width="1.6" stroke-dasharray="{"6 4" if pal in ("acct", "pub", "priv") else "none"}"/>')
            out.append(f'<text x="{x + 10}" y="{y + 18}" font-size="13" font-weight="700" fill="{text}">{escape(label)}</text>')
        else:
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>')
            lines = label.split("\n")
            lh = 14
            y0 = y + h / 2 - (len(lines) - 1) * lh / 2 + 4
            for k, ln in enumerate(lines):
                weight = "700" if k == 0 else "400"
                size = 12.5 if k == 0 else 11
                out.append(f'<text x="{x + w / 2}" y="{y0 + k * lh}" font-size="{size}" font-weight="{weight}" '
                           f'text-anchor="middle" fill="{text}">{escape(ln)}</text>')
    for src, dst, label, wps in edges:
        pts = edge_points(src, dst, wps)
        d = " ".join(f"{x},{y}" for x, y in pts)
        out.append(f'<polyline points="{d}" fill="none" stroke="#2E3A4E" stroke-width="1.5" marker-end="url(#arr)"/>')
        if label:
            # label at the midpoint of the longest segment
            segs = list(zip(pts, pts[1:]))
            (ax, ay), (bx, by) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            mx, my = (ax + bx) / 2, (ay + by) / 2
            tw = 6.2 * len(label) + 8
            out.append(f'<rect x="{mx - tw / 2}" y="{my - 9}" width="{tw}" height="16" rx="3" fill="#FFFFFF" opacity="0.92"/>')
            out.append(f'<text x="{mx}" y="{my + 3}" font-size="11" font-style="italic" text-anchor="middle" fill="#2E3A4E">{escape(label)}</text>')
    out.append("</svg>")
    return "\n".join(out)

# ---------------- draw.io ----------------
def drawio():
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for i, label, x, y, w, h, pal, cont in shapes:
        stroke, fill, text = C[pal]
        val = escape(label).replace("\n", "&lt;br&gt;")
        if cont:
            dashed = "1" if pal in ("acct", "pub", "priv") else "0"
            style = (f"rounded=1;arcSize=3;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};fontColor={text};"
                     f"dashed={dashed};verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=13;container=0;")
        else:
            lines = escape(label).split("\n")
            val = "&lt;b&gt;" + lines[0] + "&lt;/b&gt;" + "".join("&lt;br&gt;" + l for l in lines[1:])
            style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};fontColor={text};fontSize=11;"
        cells.append(f'<mxCell id="{i}" value="{val}" style="{style}" vertex="1" parent="1">'
                     f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    for n, (src, dst, label, wps) in enumerate(edges):
        pts = edge_points(src, dst, wps)
        (sx, sy), (tx, ty) = pts[0], pts[-1]
        inner = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts[1:-1])
        style = "edgeStyle=none;html=1;endArrow=block;endFill=1;strokeColor=#2E3A4E;fontSize=11;fontStyle=2;labelBackgroundColor=#FFFFFF;"
        cells.append(f'<mxCell id="e{n}" value="{escape(label)}" style="{style}" edge="1" parent="1">'
                     f'<mxGeometry relative="1" as="geometry"><mxPoint x="{sx}" y="{sy}" as="sourcePoint"/>'
                     f'<mxPoint x="{tx}" y="{ty}" as="targetPoint"/>'
                     + (f'<Array as="points">{inner}</Array>' if inner else "") +
                     '</mxGeometry></mxCell>')
    return ('<mxfile host="app.diagrams.net"><diagram id="hld" name="Company Inc. HLD">'
            f'<mxGraphModel dx="{W}" dy="{H}" grid="1" gridSize="10" guides="1" page="1" pageWidth="{W}" pageHeight="{H}">'
            '<root>' + "".join(cells) + '</root></mxGraphModel></diagram></mxfile>')

(OUT / "company-inc-hld.svg").write_text(svg())
(OUT / "company-inc-hld.drawio").write_text(drawio())
print("wrote", OUT / "company-inc-hld.svg", OUT / "company-inc-hld.drawio")
