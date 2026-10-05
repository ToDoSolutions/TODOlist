"""Adapters SCIM 2.0: User → User, Group → Organization.

``userName`` se mapea al email (nuestro USERNAME_FIELD real; el campo
``username`` interno queda como espejo). Los SCIM Groups son
``Organization``: un PUT/PATCH de members sincroniza
``OrganizationMembership`` con rol member (la provisión desde el IdP
no otorga admin — eso se decide dentro de la app).
"""
from django.contrib.auth import get_user_model
from django_scim import exceptions
from django_scim.adapters import SCIMGroup, SCIMUser


class SCIMUserAdapter(SCIMUser):
    """User ↔ recurso SCIM User (userName = email)."""

    def to_dict(self):
        d = super().to_dict()
        # userName canónico = email (los IdP lo usan como UPN)
        d["userName"] = self.obj.email
        return d

    def from_dict(self, d):
        self._scim_password = bool(d.get("password"))
        super().from_dict(d)
        # Coherencia: el login es por email; userName del IdP manda.
        username = d.get("userName")
        if username:
            self.obj.username = username
            # Si el IdP no manda emails[], el userName suele ser el email
            if not d.get("emails") and "@" in username:
                self.obj.email = username
        if not self.obj.email:
            raise exceptions.BadRequestError("emails o userName con @ requeridos")
        if self.obj.email and not self.obj.username:
            self.obj.username = self.obj.email

    def save(self):
        # Los usuarios provisionados nacen sin password usable: entran por
        # SSO o flujo de reset (salvo que el IdP envíe password explícita).
        # SCIM active=False desactiva el login.
        if not self.obj.pk and not getattr(self, "_scim_password", False):
            self.obj.set_unusable_password()
        super().save()

    def delete(self):
        """Deprovisión: desactivar la cuenta, no borrar datos."""
        self.obj.is_active = False
        self.obj.save(update_fields=["is_active"])


class SCIMOrganizationAdapter(SCIMGroup):
    """Organization ↔ recurso SCIM Group; members → OrganizationMembership."""

    @property
    def display_name(self):
        return self.obj.name

    @property
    def members(self):
        from apps.scim.adapters import SCIMUserAdapter

        dicts = []
        memberships = self.obj.memberships.select_related("user")
        for m in memberships:
            adapter = SCIMUserAdapter(m.user, self.request)
            dicts.append({
                "value": adapter.id,
                "$ref": adapter.location,
                "display": adapter.display_name,
            })
        return dicts

    def from_dict(self, d):
        super().from_dict(d)
        # Mantener ambos campos coherentes: name es el interno,
        # scim_display_name el publicado por SCIM.
        name = d.get("displayName")
        if name:
            self.obj.scim_display_name = name
        # PUT: el body completo incluye members — el adapter base lo
        # ignora (solo vía PATCH); un PUT debe sincronizar la membresía.
        members = d.get("members")
        if members is not None:
            self._replace_members(members)

    def _replace_members(self, members):
        from apps.collaboration.models import OrganizationMembership

        ids = {int(m.get("value")) for m in members or []}
        users = get_user_model().objects.filter(id__in=ids)
        if len(ids) != users.count():
            raise exceptions.BadRequestError(
                "Can not set a non-existent user as member"
            )
        keep = set(users.values_list("id", flat=True))
        self.obj.memberships.exclude(user_id__in=keep).delete()
        for u in users:
            OrganizationMembership.objects.get_or_create(
                organization=self.obj,
                user=u,
                defaults={"role": OrganizationMembership.Role.MEMBER},
            )

    def handle_add(self, path, value, operation):
        from apps.collaboration.models import OrganizationMembership

        if path.first_path == ("members", None, None):
            members = value or []
            ids = [int(member.get("value")) for member in members]
            users = get_user_model().objects.filter(id__in=ids)
            if len(ids) != users.count():
                raise exceptions.BadRequestError(
                    "Can not add a non-existent user to group"
                )
            for u in users:
                OrganizationMembership.objects.get_or_create(
                    organization=self.obj,
                    user=u,
                    defaults={"role": OrganizationMembership.Role.MEMBER},
                )
            self.save()
            return
        super().handle_add(path, value, operation)

    def handle_remove(self, path, value, operation):
        """Remove members → borra la OrganizationMembership."""
        if path.first_path == ("members", None, None):
            members = value or []
            ids = [int(member.get("value")) for member in members]
            users = get_user_model().objects.filter(id__in=ids)
            if len(ids) != users.count():
                raise exceptions.BadRequestError(
                    "Can not remove a non-existent user from group"
                )
            self.obj.memberships.filter(user__in=users).delete()
            self.save()
            return
        super().handle_remove(path, value, operation)

    def handle_replace(self, path, value, operation):
        """PUT/PATCH replace de members → reemplaza la membresía entera
        (rol member para los nuevos; los roles admin/owner manuales se
        conservan si el usuario sigue en la lista)."""
        if path.first_path == ("members", None, None):
            self._replace_members(value or [])
            self.save()
            return
        super().handle_replace(path, value, operation)
