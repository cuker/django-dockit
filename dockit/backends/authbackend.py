from dockit.models import DockitPermission
from django.contrib.auth import models as auth_app

class DockitPermissionBackend(object):
    supports_object_permissions = False
    supports_anonymous_user = True
    supports_inactive_user = True
    
    def has_module_perms(self, user_obj, app_label):
        """
        Returns True if user_obj has any permissions in the given app_label.
        """
        if not user_obj.is_active:
            return False
        for perm in self.get_all_permissions(user_obj):
            if perm[:perm.index('.')] == app_label:
                return True
        return False

def _get_permission_codename(action, opts):
    return u'%s.%s' % (opts.collection, action)

def _get_all_permissions(opts):
    "Returns (codename, name) for all permissions in the given opts."
    perms = []
    for action in ('add', 'change', 'delete'):
        perms.append((_get_permission_codename(action, opts), u'Can %s %s' % (action, opts.verbose_name_raw)))
    return perms + [('%s.%s' % (opts.collection, perm), name) for perm, name in opts.permissions]

#code => <collection>.code
#content type = DockitPermission

#user.has_perm(dockit.somecollection.code)

def create_permissions(documents, verbosity, **kwargs):
    from django.contrib.contenttypes.models import ContentType

    # This will hold the permissions we're looking for as
    # (content_type, (codename, name))
    searched_perms = list()
    ctype = ContentType.objects.get_for_model(DockitPermission)
    # The codenames and ctypes that should exist.
    for klass in documents:
        for perm in _get_all_permissions(klass._meta):
            searched_perms.append(perm)

    # Find all the Permissions that have a context_type for a model we're
    # looking for.  We don't need to check for codenames since we already have
    # a list of the ones we're going to create.
    all_perms = set(auth_app.Permission.objects.filter(
        content_type=ctype,
    ).values_list(
        "codename", flat=True
    ))

    for codename, name in searched_perms:
        # If the permissions exists, move on.
        if codename in all_perms:
            continue
        p = auth_app.Permission.objects.create(
            codename=codename,
            name=name,
            content_type=ctype
        )
        if verbosity >= 2:
            print "Adding permission '%s'" % p

def on_document_registered(document, **kwargs):
    create_permissions([document], 1)
