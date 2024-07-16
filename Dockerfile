FROM kitware/trame

RUN apt update && apt install -y libx11-6 libgl1 libxrender1 libgl1-mesa-dev xvfb vim

COPY --chown=trame-user:trame-user . /deploy
COPY --chown=trame-user:trame-user ./vtk /vtk
COPY --chown=trame-user:trame-user ./tif /tif

ENV TRAME_CLIENT_TYPE=vue2
ENV DISPLAY=:99.0
ENV PYVISTA_OFF_SCREEN=true

RUN Xvfb :99 -nolisten tcp -fbdir /var/run > /dev/null 2>&1 &

RUN /opt/trame/entrypoint.sh build && sed -i "s/wms = owslib.wms.WebMapService(url)/wms = owslib.wms.WebMapService(url,version='1.3.0')/g" /deploy/server/venv/lib/python3.9/site-packages/gemgis/web.py