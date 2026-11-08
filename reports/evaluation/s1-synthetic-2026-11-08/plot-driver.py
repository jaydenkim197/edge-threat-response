"""Export a static figure from completed S1 aggregate CSV; no new inference."""
from pathlib import Path
import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

run=Path(r'C:\Class6\edge-threat-response\runs\s1-comparison-20261108-v1')
out=run/'analysis'
table=list(csv.DictReader((run/'predict/aggregate/comparison.csv').open(encoding='utf-8-sig')))
names=['raw-m1-n-640','raw-m2-n-640','raw-s1-n-640']
datasets=['sohas-test','dasci-unique','open-images','simuletic','us-mock-reviewed']
short=['SOHAS test\nN=23\nGT=20','DaSCI\nN=92\nGT=97','Open Images\nN=29\nGT=39','Synthetic CCTV\nN=75\nGT=63','Real CCTV\nN=83\nGT=31']
plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'etr-s1-20261108'})
fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
for ax,metric,title in zip(axes,['ap50','recall025'],['Knife AP50 (%)','Knife recall at confidence 0.25 (%)']):
 data=np.array([[100*float(next(r[metric] for r in table if r['model']==m and r['dataset']==d)) for d in datasets] for m in names])
 im=ax.imshow(data,vmin=0,vmax=100,cmap='Blues',aspect='auto')
 ax.set_yticks(range(3),['M1: real baseline','M2: + Open Images','S1: M2 + synthetic'],fontsize=9)
 ax.set_xticks(range(5),short,fontsize=8)
 ax.set_title(title,fontsize=12,pad=12)
 for y in range(3):
  for x in range(5): ax.text(x,y,f'{data[y,x]:.1f}',ha='center',va='center',fontsize=11,color='white' if data[y,x]>60 else '#172538')
 fig.colorbar(im,ax=ax,shrink=.8,pad=.02)
fig.suptitle('M1 / M2 / S1: identical opened development evaluation | YOLO26n, 640 px',fontsize=13)
fig.supxlabel('FP32, batch 1, same inputs and GT. Matching IoU 0.5. Synthetic results do not establish real-CCTV performance.\nSOHAS test has already been opened for development; this is not independent final evaluation.',fontsize=9)
for ext in ['png','svg','pdf']: fig.savefig(out/('m1-m2-s1.'+ext),dpi=200)
plt.close(fig)
(out/'plot-environment.json').write_text(json.dumps({'matplotlib':matplotlib.__version__,'numpy':np.__version__},indent=2)+'\n')
print('Exported PNG/SVG/PDF')
