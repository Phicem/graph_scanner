import matplotlib.pyplot as plt
import numpy as np

x=np.array(range(100))
y=(x/10.)**2

fig, axes = plt.subplots(figsize=(10,6))

axes.plot(x, y, 'r')
axes.set_xlabel('x')
axes.set_ylabel('y')
axes.set_title('title');

plt.show()
