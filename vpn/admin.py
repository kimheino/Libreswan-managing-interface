# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import subprocess
import os
import string
import random
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import SubnetToSubnet, VpnForRemoteHost, GenerateCertificate, UserProfile, CertificateConfiguration, GeneratePrivateKey, GenerateRootCertificate, PrivateKeyPassword

# Register your models here.
""" Defining global variables for using in multiple functions
    tempdirname - Temporary certificates holding directory name
    dirname - Final .p12 certificates holding directory name
    configdirname - Directory holding configuration files
    distributionlistdir - Directory for saving the distribution list CRL file
    PassKeyName - Name of the CA private key as stored in database
"""


tempdirname = 'temp_cert/'
dirname = 'certs/'
configdirname = 'config/'
distributionlistdir = configdirname + 'crl/'
PassKeyName = 'privatekey'


""" write_to_file function -
    writing data to /etc/ipsec.d/connection_name.conf file so that the connection can be saved and loaded from the /etc/ipsec.d/* directory without disturbing other connections
    Opening file in w+ mode, as it will create the file if it doesn't exist otherwise write it
    Checking If attribute exists and has a value, so as to avoid writing attributes with no value to the configuration file
    Writing to file the non empty attributes and their respective value
"""


def write_to_file(modeladmin, request, queryset):
    ConnectionsList = []
    SubnetOrVpn = 0
    for qs in queryset:
        list_values = [
            'also', 'left', 'leftsubnet', 'right', 'rightsubnet',
            'keyringtries', 'auto', 'leftcert', 'leftid', 'leftsendcert',
            'leftrsasigkey', 'rightaddresspool', 'rightca', 'modecfgdns',
            'narrowing', 'dpddelay', 'dpdtimeout', 'dpdaction', 'ikev2',
            'rekey', 'fragmentation', 'mobike'
        ]
        lastval = len(list_values)
        file = "/etc/ipsec.d/" + qs.connection_name + ".conf"
        f = open(file, 'w+')
        f.write("conn " + qs.connection_name + "\n")
        for i in range(0, lastval):
            current = list_values[i]
            if (hasattr(qs, current) and getattr(qs, current) != ''):
                f.write("\t" + current + "=" + getattr(qs, current) + "\n")
                if current == 'leftcert':
                    SubnetOrVpn = 1
        f.write("\n")
        f.close()

        # Adding connection name to the Connectionslist, So as to give a single success notification/prompt for all connections
        ConnectionsList.append(qs.connection_name)
        if SubnetOrVpn == 1:
            #ipsec auto --add <conname>
            cmd = [
                'ipsec', 'auto', '--add',
                '/etc/ipsec.d/' + qs.connection_name + '.conf'
            ]
        else:
            cmd = [
                'ipsec', 'auto', '--start',
                '/etc/ipsec.d/' + qs.connection_name + '.conf'
            ]
        s = subprocess.Popen(cmd, shell=False)
        out, err = s.communicate('\n')

    # Displaying success message for certificate generation
    allconnections = ', '.join(ConnectionsList)
    messages.success(request, "Connection profiles: " + allconnections +
                     " created/updated successfully.")


""" write_configuration_to_file function -
    It writes the selected user configuration to the default configuration file,
    The values will be loaded from this file while generating the certificates.
    In this way user can create as many configurations as he wants and has the option to choose any configuration as default.
    All the certificates generated will use the saved(written to file) configuration.
"""


def write_configuration_to_file(modeladmin, request, queryset):

    # Creating directory for saving certificates
    if (os.path.isdir(configdirname) != True):
        os.makedirs(configdirname, 0o755, True)

        # Success message on folder creation
        messages.success(request,
                         "Directory for saving default configuration file: `" +
                         configdirname + "` created successfully.")

    for qs in queryset:
        qs.expiration_period = str(qs.expiration_period)
        list_values = [
            'expiration_period', 'country_name', 'state_province',
            'locality_name', 'organization_name', 'organization_unit',
            'common_name', 'email_address'
        ]
        lastval = len(list_values)
        file = configdirname + "default_certificate.conf"
        f = open(file, 'w+')
        for i in range(0, lastval):
            current = list_values[i]
            if (hasattr(qs, current) and getattr(qs, current) != ''):
                f.write(getattr(qs, current) + "\n")
        f.close()

    # Displaying success message on saving default_configuration file
    messages.success(request, "Default Certificate configuration file: `" +
                     configdirname + "default_certificate.conf` updated.")


write_configuration_to_file.short_description = "Save Configuration as Default configuration"


""" Check if folder exists/create folder for storing the certificates
    this function is checking if the temporary and the final certificates holding dierctories exists
"""


def check_folders(request):
    #for saving user certificates and keys (.pem & .csr files)
    if (os.path.isdir(tempdirname) != True):
        os.makedirs(tempdirname, 0o755, True)

        # Success message on folder creation
        messages.success(request,
                         "Directory for saving user certificates and keys: " +
                         tempdirname + " created successfully.")

    #for saving final .p12 certificates
    if (os.path.isdir(dirname) != True):
        os.makedirs(dirname, 0o755, True)

        # Success message on folder creation
        messages.success(request, "Directory for saving .p12 certificates: " +
                         dirname + " created successfully.")

    #for saving the distribution list (.crl) file
    if (os.path.isdir(distributionlistdir) != True):
        os.makedirs(distributionlistdir, 0o755, True)

        # Success message on folder creation
        messages.success(request, "Directory for saving distribution list " +
                         distributionlistdir + " created successfully.")


# Generate random name, will be used to assign name to cert and keys
def random_name(leng, ntype):
    gen_name = ''.join(
        random.SystemRandom().choice(string.ascii_lowercase + string.digits)
        for _ in range(leng)) + ntype
    return gen_name


# Generating temporary rsa key pair/certificates, will be used to create .p12 files
def gen_temp_keys(keyname, certname, username):
    #Fetch default configuration from file to write it to the certs
    DefaultConfigFile = open(configdirname + 'default_certificate.conf', 'r')
    FileContent = DefaultConfigFile.readlines()
    ExpirationPeriod = FileContent[0]
    CountryName = FileContent[1]
    StateProvince = FileContent[2]
    LocalityName = FileContent[3]
    OrgName = FileContent[4]
    OrgUnit = FileContent[5]
    CommonName = FileContent[6]
    EmailAddress = FileContent[7]

    if CommonName.strip('\n') == "user":
        CommonName = username

    #Generate the key for the user, to be used to generate user certificate
    cmd = [
        'openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout',
        tempdirname + keyname + '.pem', '-days', ExpirationPeriod
    ]
    r = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=False)
    # writing the values to PIPE
    r.stdin.write(CountryName.encode())
    r.stdin.write(StateProvince.encode())
    r.stdin.write(LocalityName.encode())
    r.stdin.write(OrgName.encode())
    r.stdin.write(OrgUnit.encode())
    r.stdin.write(CommonName.encode())
    r.stdin.write(EmailAddress.encode())
    r.stdin.write(EmailAddress.encode())
    r.stdin.write(OrgName.encode())
    # getting the output/errors
    out, err = r.communicate('\n'.encode())
    r.stdin.close()

    #Generating a Certificate Signing Request from the above obtained key, to be used to sign the CSR hence certificate with the CA key
    cmd = [
        'openssl', 'req', '-out', tempdirname + keyname + '.csr', '-key',
        tempdirname + keyname + '.pem', '-new', '-days', ExpirationPeriod
    ]
    r = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=False)
    # writing the values to PIPE
    r.stdin.write(CountryName.encode())
    r.stdin.write(StateProvince.encode())
    r.stdin.write(LocalityName.encode())
    r.stdin.write(OrgName.encode())
    r.stdin.write(OrgUnit.encode())
    r.stdin.write(CommonName.encode())
    r.stdin.write(EmailAddress.encode())
    r.stdin.write(EmailAddress.encode())
    r.stdin.write(OrgName.encode())
    # getting the output/errors
    out, err = r.communicate('\n'.encode())
    r.stdin.close()

    #getting the ca key password, to sign the certs
    KeyFinalPassword = PrivateKeyPassword.objects.get(key_name=PassKeyName)
    KeyFinalPassword = KeyFinalPassword.priv_key_password

    #signing the key with root cert, so as all the keys and .p12 files become signed by a CA
    cmd = [
        'openssl', 'ca', '-batch', '-create_serial', '-config',
        configdirname + 'openssl.cnf', '-cert',
        configdirname + 'private/ca.root.pem', '-keyfile',
        configdirname + 'private/ca.key.pem', '-passin',
        'pass:' + KeyFinalPassword, '-in', tempdirname + keyname + '.csr',
        '-out', tempdirname + certname, '-extensions', 'usr_cert'
    ]
    r = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=False)
    out, err = r.communicate('\n'.encode())
    r.stdin.close()

    os.chmod(tempdirname + keyname + '.pem', 0o400)


# Generate .p12 certificates, will be used to establish connection
def gen_p12_cert(keyname, certname, password, username):
    cmd = [
        'openssl', 'pkcs12', '-name', username, '-inkey',
        tempdirname + keyname + '.pem', '-in', tempdirname + certname,
        '-export', '-out', dirname + username + '.p12', '-password',
        'pass:' + password
    ]
    s = subprocess.Popen(cmd, shell=False)
    out, err = s.communicate('\n'.encode())

    os.chmod(dirname + username + '.p12', 0o400)


# Delete temporary certificates, as .p12 file is generated and they're no longer required
def dlt_temp_cert(filename):
    cmd = ['rm', '-rf', tempdirname + filename]
    s = subprocess.Popen(cmd, shell=False)
    out, err = s.communicate('\n'.encode())


# Delete .p12 files when user data is deleted
def dlt_p12_cert(filename):
    cmd = ['rm', '-rf', dirname + filename]
    s = subprocess.Popen(cmd, shell=False)
    out, err = s.communicate('\n'.encode())


""" Generate user certificate -
    Steps for generating temporary/intermediate certificates:
    Step 1 [Generate random names for certs(public and private)] - Get random name for certificate and key, as every key and cert will be unique this will save from any certificate/key overwriting
    Step 2 [Generate private and public keys] - Generate intermediate certificates, these will be used to generate the final .p12 certs
    Step 3 [Create .p12 file using the above keys] - Generating the .p12 certificates, they are the final certs which will be used to establish connections
    Step 4 [Delete the certificate signing request generated in Step 2] - Delete the temporary CSR, as they were only required to sign the certificates.
    Step 5 [Save the information to database] - Save/Update the password of certificates in/to database, as it'll be shown to user after his successfull login into the portal
"""


def generate_user_certificate(self, request, queryset):
    check_folders(request)
    UsersList = []
    # For each qs in queryset generate the certificates. Taking input username, it'll be the name of the final generated certificate
    for qs in queryset:
        username = str(qs.username)
        keyname = random_name(10, '')
        certname = random_name(10, '.pem')
        gen_temp_keys(keyname, certname, username)
        password = random_name(20, '')
        gen_p12_cert(keyname, certname, password, username)
        dlt_temp_cert(keyname + '.csr')

        GenerateCertificate.objects.filter(username__username=username).update(
            cert_name=certname)
        GenerateCertificate.objects.filter(username__username=username).update(
            cert_password=password)
        GenerateCertificate.objects.filter(username__username=username).update(
            key_name=keyname)
        #fetching the userid from the User model, to update the certificate_revocation value
        userid = User.objects.get(username=username)
        userid = userid.id
        #Updating the certificate_revocation value in database
        UserProfile.objects.filter(username_id=userid).update(
            certificate_revoked=False)

        # Adding user to the userslist, So as to give a single success notification/prompt for all connections
        UsersList.append(username)

    # Displaying success message for certificate generation
    allusers = ', '.join(UsersList)
    messages.success(
        request,
        "Certificates for users: " + allusers + " generated successfully.")


""" Revoke user certificate -
    Steps for revoking user certificates:
    Step 1 - Get the username and the certname
    Step 2 - Revoke the certificate using the command `openssl ca -config intermediate/openssl.cnf -revoke intermediate/certs/bob@example.com.cert.pem`
    Step 3 - Once revocation completes create a dir if not already exists `config/crl`, this will save the `distribution.crl` list in it. The list is available on public IP at `http://HOSTNAME//crl/distripoint.crl`
    Step 4 - Once the above directory is created recreate the CRL(certificate revocation list) using the command `openssl ca -config intermediate/openssl.cnf -gencrl -out intermediate/crl/intermediate.crl.pem`
"""


def revoke_user_certificate(self, request, queryset):

    UsersList = []
    for qs in queryset:
        username = str(qs.username)
        certname = str(qs.cert_name)

        #fetching the private key password, will be used while certificate revocation
        KeyPassword = PrivateKeyPassword.objects.get()
        KeyPassword = KeyPassword.priv_key_password

        #revoking the user certificate
        cmd = [
            'openssl', 'ca', '-config', configdirname + 'openssl.cnf',
            '-revoke', tempdirname + certname, '-passin', 'pass:' + KeyPassword
        ]
        r = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=False)
        out, err = r.communicate('\n'.encode())

        #fetching the userid from the User model, to update the certificate_revocation value
        userid = User.objects.get(username=username)
        userid = userid.id
        #Updating the certificate_revocation value in database
        UserProfile.objects.filter(username_id=userid).update(
            certificate_revoked=True)

        UsersList.append(username)

    allusers = ', '.join(UsersList)

    #displaying the success message to admin
    messages.success(
        request,
        "Certificates for users: " + allusers + " revoked successfully.")

    #recreating the certificate revocation list after each certificate revocation
    cmd = [
        'openssl', 'ca', '-config', configdirname + 'openssl.cnf', '-gencrl',
        '-out', distributionlistdir + 'distripoint.crl', '-passin',
        'pass:' + KeyPassword
    ]
    r = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=False)
    out, err = r.communicate('\n'.encode())

    #displaying the success message to admin
    messages.success(request,
                     "Certificate revocation list updated successfully.")


# Save key as private function, creates and saves the CA private key
def save_key_as_private_key(self, request, queryset):

    # Creating directory for saving certificates
    if (os.path.isdir(configdirname + 'private/') != True):
        os.makedirs(configdirname + 'private/', 0o755, True)

        # Success message on folder creation
        messages.success(
            request,
            "Directory for saving private key & root certificate created successfully."
        )

    for qs in queryset:
        KeyPassword = qs.key_password

        cmd = [
            'openssl', 'genrsa', '-aes256', '-out',
            configdirname + 'private/ca.key.pem', '-passout',
            'pass:' + KeyPassword, '4096'
        ]
        r = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=False)
        # getting the output/errors
        out, err = r.communicate('\n'.encode())
        r.stdin.close()

        #saving the private key password to database, so that it can be used while signing the certificates
        keypassword = PrivateKeyPassword(
            key_name=PassKeyName, priv_key_password=KeyPassword)
        keypassword.save()

        os.chmod(configdirname + 'private/ca.key.pem', 0o400)

    messages.success(request, "Key successfully saved as private key.")


# Generate root certificate function, creates and saves the CA root certificate
def generate_root_certificate(self, request, queryset):

    # Creating directory for saving certificates
    if (os.path.isdir(configdirname + 'private/') != True):
        os.makedirs(configdirname + 'private/', 0o700, True)

        # Success message on folder creation
        messages.success(
            request,
            "Directory for saving private key & root certificate created successfully."
        )

    for qs in queryset:
        qs.expiration_period = str(qs.expiration_period)
        SetPassword = PrivateKeyPassword.objects.get(key_name=PassKeyName)
        SetPassword = SetPassword.priv_key_password

        list_values = [
            'expiration_period', 'country_name', 'state_province',
            'locality_name', 'organization_name', 'organization_unit',
            'common_name', 'email_address'
        ]
        lastval = len(list_values)
        file = configdirname + "private/root_certificate.conf"
        f = open(file, 'w+')
        for i in range(0, lastval):
            current = list_values[i]
            if (hasattr(qs, current) and getattr(qs, current) != ''):
                f.write(getattr(qs, current) + "\n")
        f.close()

        #Fetch configuration from file to write it to the certs
        DefaultConfigFile = open(
            configdirname + 'private/root_certificate.conf', 'r')
        FileContent = DefaultConfigFile.readlines()
        ExpirationPeriod = FileContent[0]
        CountryName = FileContent[1]
        StateProvince = FileContent[2]
        LocalityName = FileContent[3]
        OrgName = FileContent[4]
        OrgUnit = FileContent[5]
        CommonName = FileContent[6]
        EmailAddress = FileContent[7]

        cmd = [
            'openssl', 'req', '-key', configdirname + 'private/ca.key.pem',
            '-passin', 'pass:' + SetPassword, '-new', '-x509', '-days',
            ExpirationPeriod, '-sha256', '-out',
            configdirname + 'private/ca.root.pem', '-config',
            configdirname + 'openssl.cnf'
        ]
        r = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=False)
        # writing the values to PIPE
        r.stdin.write(CountryName.encode())
        r.stdin.write(StateProvince.encode())
        r.stdin.write(LocalityName.encode())
        r.stdin.write(OrgName.encode())
        r.stdin.write(OrgUnit.encode())
        r.stdin.write(CommonName.encode())
        r.stdin.write(EmailAddress.encode())
        # getting the output/errors
        out, err = r.communicate('\n'.encode())
        r.stdin.close()

        os.chmod(configdirname + 'private/ca.root.pem', 0o400)
        os.remove(configdirname + 'private/root_certificate.conf')

    messages.success(request, "Root certificate successfully generated.")


# Disable user function, this is being used to disable user profile. So, as to prevent user login into this portal
def DisableUser(self, request, queryset):
    UsersList = []
    for qs in queryset:
        user = qs.username
        active = qs.is_active
        User.objects.filter(username=user).update(is_active=False)
        UsersList.append(user)

    # Displaying success message for disabling user
    allusers = ', '.join(UsersList)
    messages.success(request,
                     "The users: " + allusers + " Disabled successfully. These users can't login to this interface now.")


DisableUser.short_description = "Disable User (Disallow User to Login)"


# Enable user function, this is enabling(reactivating) the disabled user. So, that user can login to the portal and do the required things
def EnableUser(self, request, queryset):
    UsersList = []
    for qs in queryset:
        user = qs.username
        active = qs.is_active
        User.objects.filter(username=user).update(is_active=True)
        UsersList.append(user)

    # Displaying success message for enabling user
    allusers = ', '.join(UsersList)
    messages.success(request,
                     "The users: " + allusers + " Enabled successfully. These users can now login to this interface.")


EnableUser.short_description = "Enable User (Allow User to Login)"


# Delete user data will delete all the certificates generated for user
def DeleteUserData(self, request, queryset):
    UsersList = []
    for qs in queryset:
        username = str(qs.username)
        #get user data from database
        user = GenerateCertificate.objects.get(username__username=username)
        keyname = user.key_name
        certname = user.cert_name

        #deleting the certificates from system
        dlt_temp_cert(keyname + '.pem')
        dlt_temp_cert(certname + '.pem')
        dlt_p12_cert(username + '.p12')

        #deleting the user data from database
        GenerateCertificate.objects.filter(username__username=username).update(
            cert_name='')
        GenerateCertificate.objects.filter(username__username=username).update(
            cert_password='')
        GenerateCertificate.objects.filter(username__username=username).update(
            key_name='')
        UserProfile.objects.filter(username__username=username).update(
            certificate_revoked=False)
        UsersList.append(username)

    # Displaying success message for disabling user
    allusers = ', '.join(UsersList)
    messages.success(request,
                     "The users: " + allusers + " data deleted successfully.")


DeleteUserData.short_description = "Delete User Data (Keys & Certificates)"


# Deletes all the user certificates and resets the index and serial along with the crlnumber (user to generate the CR list)
def DeleteAllUserCertificates(self, request, queryset):
    
    #delete certs/ directory
    cmd = ['rm', '-rf', dirname]
    s = subprocess.Popen(cmd, shell=False)
    out, err = s.communicate('\n'.encode())

    #delete temp_certs/ directory
    cmd = ['rm', '-rf', tempdirname]
    s = subprocess.Popen(cmd, shell=False)
    out, err = s.communicate('\n'.encode())

    #delete CA certificates directory
    cmd = ['rm', '-rf', configdirname + 'private/']
    s = subprocess.Popen(cmd, shell=False)
    out, err = s.communicate('\n'.encode())

    #delete certificates info and certificate conf file
    cmd = [
        'rm', '-rf', configdirname + 'index.txt.attr',
        configdirname + 'index.txt.attr.old', configdirname + 'index.txt.old',
        configdirname + 'serial.old', configdirname + 'default_certificate.conf'
    ]
    s = subprocess.Popen(cmd, shell=False)
    out, err = s.communicate('\n'.encode())

    #delete contents from index.txt file
    f = open(configdirname + 'index.txt', 'w+')
    f.close()

    #add 01 as starting no. in serial file
    f = open(configdirname + 'serial', 'w+')
    f.write('01')
    f.close()

    #delete files from crl directory
    cmd = [
        'rm', '-rf', distributionlistdir + 'crlnumber.old',
        distributionlistdir + 'distripoint.crl'
    ]
    s = subprocess.Popen(cmd, shell=False)
    out, err = s.communicate('\n'.encode())

    #add 01 as starting no. on crlnumber
    f = open(distributionlistdir + 'crlnumber', 'w+')
    f.write('01')
    f.close()
    
    #resetting the keys & certificates values in database
    keys_and_certs = {'cert_name': '', 'cert_password': '', 'key_name': ''}
    cert_revoke = {'certificate_revoked':False}
    GenerateCertificate.objects.all().update(**keys_and_certs)
    UserProfile.objects.all().update(**cert_revoke)

    # Displaying success message
    messages.success(request,
                     "All User & CA certificates deleted successfully.")

DeleteAllUserCertificates.short_description = "Delete all certificates (User & CA)"

# Creating admin task options as this will display(list_display) info in the admin panel
class TaskAdmin(admin.ModelAdmin):
    list_display = ['connection_name', 'creation_date']
    actions = [write_to_file]


class TaskConfigureAdmin(admin.ModelAdmin):
    list_display = [
        'organization_name', 'organization_unit', 'common_name',
        'email_address', 'expiration_period'
    ]
    actions = [write_configuration_to_file]


class TaskConfigureRoot(admin.ModelAdmin):
    list_display = ['key_name', 'key_password']
    actions = [save_key_as_private_key]


class TaskConfigureRootCert(admin.ModelAdmin):
    list_display = [
        'organization_name', 'organization_unit', 'common_name',
        'email_address', 'expiration_period'
    ]
    actions = [generate_root_certificate]


# Define an inline admin descriptor for UserDetail model, this is displaying a model(GenerateCertificates) into default user model
class UserDetailInline(admin.StackedInline):
    model = GenerateCertificate
    can_delete = False
    verbose_name_plural = 'User Details'


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profiles'


# Define a new User admin, this is the default user admin model
class UserAuthAdmin(BaseUserAdmin):
    list_display = [
        'username', 'email', 'is_active', 'last_login', 'date_joined'
    ]
    actions = [DeleteUserData, EnableUser, DisableUser, DeleteAllUserCertificates]
    inlines = (UserDetailInline, UserProfileInline)


# UserAdmin Class for new model, this will allow the required actions to be done from a different models and not just from the default admin/user model
class UserAdmin(admin.ModelAdmin):
    list_display = [
        'username', 'email_verified', 'certificate_revoked', 'cert_name',
        'cert_password', 'key_name'
    ]

    # Fetching the email_verified field from UserProfile Model for accessibility
    def email_verified(self, obj):
        return obj.username.userprofile.email_verified

    # Fetching the certificate_revoked field from UserProfile Model for accessibility
    def certificate_revoked(self, obj):
        return obj.username.userprofile.certificate_revoked

    # Using boolean fields for convenience
    email_verified.boolean = True
    certificate_revoked.boolean = True

    actions = [generate_user_certificate, revoke_user_certificate, DeleteUserData, DeleteAllUserCertificates]


# Changing Admin header text, this is done to customize the Admin interface
admin.site.site_header = 'Libreswan Administration'

#Displaying the models to admin
admin.site.unregister(User)
admin.site.register(SubnetToSubnet, TaskAdmin)
admin.site.register(VpnForRemoteHost, TaskAdmin)
admin.site.register(CertificateConfiguration, TaskConfigureAdmin)
admin.site.register(User, UserAuthAdmin)
admin.site.register(GeneratePrivateKey, TaskConfigureRoot)
admin.site.register(GenerateRootCertificate, TaskConfigureRootCert)
admin.site.register(GenerateCertificate, UserAdmin)
