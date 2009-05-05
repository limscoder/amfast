"""Generates Actionscript code from ClassDef objects."""
import os

class CodeGenerator(object):
    """Generates Actionscript source code from class defs.

    attributes:
    ============
     * indent - string, indention string to use. Default = '\t'
    """

    def __init__(self, indent='\t'):
        self.indent = indent

    def generateFilesFromMapper(self, class_mapper, dir='.', use_accessors=False,
        packaged=False, constructor=False, bindable=False,
        extends=None, implements=None):
        """Generates an Actionscript class files.

        arguments:
        ===========
         * class_mapper - amfast.class_def.ClassDefMapper, ClassDefMapper being used to generate the action script classes.
         * dir - string, directory to store generated files in. Default = '.'
         * use_accessors - bool, If True create getter and setter methods for attributes. Default = False
         * packaged - bool, If True wrap created class in a package (for AS3). Default = False
         * constructor - bool, If True create a constructor method. Default = False
         * bindable - bool, If True, add the 'Bindable' metadata tag. Default = False
         * extends - string, name of the class that this class inherits from. Default = None
         * implements - list or tuple, a list of interface names that this class implments. Default = None
        """
        for class_def in class_mapper:
            if class_def._built_in is True:
                continue

            self.generateClassFile(class_def, dir, use_accessors,
                packaged, constructor, bindable, extends, implements)

    def generateClassFile(self, class_def, dir='.', use_accessors=False,
        packaged=False, constructor=False, bindable=False,
        extends=None, implements=None):
        """Generates an Actionscript class source file.

        arguments:
        ===========
         * class_def - amfast.class_def.ClassDef, ClassDef being used to generate the action script class.
         * dir - string, directory to store generated files in. Default = '.'
         * use_accessors - bool, If True create getter and setter methods for attributes. Default = False
         * packaged - bool, If True wrap created class in a package (for AS3). Default = False
         * constructor - bool, If True create a constructor method. Default = False
         * bindable - bool, If True, add the 'Bindable' metadata tag. Default = False
         * extends - string, name of the class that this class inherits from. Default = None
         * implements - list or tuple, a list of interface names that this class implments. Default = None
        """
        package = class_def.alias.split('.')
        class_ = package.pop()

        # Create all output directories
        path = dir
        for i in range(0, len(package)):
            path = os.path.join(path, package[i])
            if os.path.exists(path) is not True:
                os.mkdir(path)

        out = open(os.path.join(path, '%s.as' % class_), 'w')
        out.write(self.generateClassStr(class_def, use_accessors, packaged,
            constructor, bindable, extends, implements))
        out.close()

    def generateClassStr(self, class_def, use_accessors=False,
        packaged=False, constructor=False, bindable=False,
        extends=None, implements=None):
        """Generates an Actionscript class source string.

        arguments:
        ===========
         * class_def - amfast.class_def.ClassDef, ClassDef being used to generate the action script class.
         * use_accessors - bool, If True create getter and setter methods for attributes. Default = False
         * packaged - bool, If True wrap created class in a package (for AS3). Default = False
         * constructor - bool, If True create a constructor method. Default = False
         * bindable - bool, If True, add the 'Bindable' metadata tag. Default = False
         * extends - string, name of the class that this class inherits from. Default = None
         * implements - list or tuple, a list of interface names that this class implments. Default = None
        """
        class_str = []

        package = class_def.alias.split('.')
        class_ = package.pop()
        package = '.'.join(package)
        indent = ''

        if packaged is True:
           class_str.append('package %s' % package)
           class_str.append('{')
           indent = self.indent

        if bindable is True:
            class_str.append(indent + '[Bindable]')

        class_str.append(indent + "[RemoteClass(alias='%s')]" % class_def.alias)

        class_def_str = indent
        if packaged is True:
            class_def_str += 'public '
        
        if hasattr(class_def, "DYNAMIC_CLASS_DEF") is True:
            class_def_str += 'dynamic '

        if hasattr(class_def, "EXTERNIZEABLE_CLASS_DEF") is True:
            imp = ['IExternalizable']
            if implements is not None:
                imp.extend(implements)
            implements = imp

        class_def_str += 'class %s' % class_
        if extends is not None:
            class_def_str += ' extends %s' % extends

        if implements is not None and len(implements) > 0:
            class_def_str += ' implements %s' % ', '.join(implements)

        class_str.append(class_def_str);
        class_str.append(indent + '{')
        for attr in class_def.static_attrs:
            if use_accessors is True:
                class_str.append(self.generateAccessor(attr, indent + self.indent))
            else:
                class_str.append(indent + self.indent + 'public var %s:Object;' % attr)

        if constructor is True:
            class_str.append('\n' + indent + self.indent + 'public function %s():void' % class_)
            class_str.append(indent + self.indent + '{')
            if extends is not None:
                class_str.append(indent + self.indent + self.indent + 'super();')
            class_str.append(indent + self.indent + '}')

        class_str.append(indent + '}')
        if packaged is True:
            class_str.append('}')
        return '\n'.join(class_str)

    def generateAccessor(self, attr, indent=''):
        """Generates an Actionscript getter and setter source string.

        arguments:
        ===========
         * attr - string, the attribute name to generate code for.
         * indent - string, indent to add to generated code. Default = ''.
        """
        attr_str = []
        attr_str.append('\n' + indent + "private var _%s:Object;" % attr)

        attr_str.append(indent + "public function get %s():Object" % attr)
        attr_str.append(indent + "{")
        attr_str.append(indent + self.indent + "return _%s;" % attr)
        attr_str.append(indent + "}")

        attr_str.append('\n' + indent + "public function set %s(value:Object):void" % attr)
        attr_str.append(indent + "{")
        attr_str.append(indent + self.indent + " _%s = value;" % attr)
        attr_str.append(indent + "}")

        return '\n'.join(attr_str);
