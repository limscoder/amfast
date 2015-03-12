# Code Generation #

  * ClassDefMapper and ClassDef can be used to generate Actionscript source code.
  * Use the class\_def.code\_generator.CodeGenerator class.

```
from amfast.class_def.code_generator import CodeGenerator   

coder = CodeGenerator()
coder.generateFilesFromMapper(class_def_mapper, use_accessors=True,
    packaged=True, constructor=True, bindable=True, extends='Parent')
```