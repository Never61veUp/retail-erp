FROM odoo:19.0

COPY --chown=odoo:odoo ./addons /mnt/extra-addons
COPY --chown=odoo:odoo ./config/odoo.conf /etc/odoo/odoo.conf

USER root
COPY --chown=root:root ./docker-entrypoint.sh /usr/local/bin/retail-erp-entrypoint
RUN chmod 755 /usr/local/bin/retail-erp-entrypoint
USER odoo

ENTRYPOINT ["/usr/local/bin/retail-erp-entrypoint"]
CMD ["odoo"]
